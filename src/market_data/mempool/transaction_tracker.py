"""
Transaction Tracker

Tracks pending and confirmed transactions for:
- Trade execution monitoring
- Slippage analysis
- Success/failure tracking
- Performance metrics
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

from src.market_data.mempool.mempool_monitor import MempoolTransaction, ChainType


class TransactionStatus(Enum):
    """Transaction status states."""
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED" 
    FAILED = "FAILED"
    DROPPED = "DROPPED"
    REPLACED = "REPLACED"


@dataclass
class TrackedTransaction:
    """Enhanced transaction tracking data."""
    mempool_tx: MempoolTransaction
    status: TransactionStatus = TransactionStatus.PENDING
    confirmation_time: Optional[datetime] = None
    block_number: Optional[int] = None
    gas_used: Optional[int] = None
    effective_gas_price: Optional[float] = None
    
    # DEX-specific tracking
    actual_amount_out: Optional[float] = None
    slippage_pct: Optional[float] = None
    price_impact_pct: Optional[float] = None
    
    # Performance tracking
    submitted_time: datetime = field(default_factory=datetime.now)
    confirmed_time: Optional[datetime] = None
    total_time_seconds: Optional[float] = None


@dataclass
class TransactionMetrics:
    """Transaction performance metrics."""
    total_tracked: int = 0
    confirmed: int = 0
    failed: int = 0
    dropped: int = 0
    avg_confirmation_time: float = 0.0
    avg_gas_used: float = 0.0
    avg_slippage: float = 0.0
    success_rate: float = 0.0


class TransactionTracker:
    """
    Tracks transaction lifecycle and performance.
    
    Features:
    - Pending transaction monitoring
    - Confirmation tracking
    - Slippage analysis
    - Performance metrics
    - Failed transaction analysis
    """
    
    def __init__(self, max_tracking_hours: int = 24):
        self.max_tracking_hours = max_tracking_hours
        self.logger = logging.getLogger(__name__)
        
        # Transaction storage
        self._tracked_transactions: Dict[str, TrackedTransaction] = {}
        self._completed_transactions: List[TrackedTransaction] = []
        
        # Performance metrics
        self._metrics_by_chain: Dict[ChainType, TransactionMetrics] = {}
        
        # Configuration
        self._confirmation_timeouts = {
            ChainType.ETHEREUM: 300,    # 5 minutes
            ChainType.POLYGON: 60,      # 1 minute
            ChainType.ARBITRUM: 120,    # 2 minutes
            ChainType.OPTIMISM: 120,    # 2 minutes
            ChainType.BSC: 60          # 1 minute
        }
        
        self.logger.info("Transaction Tracker initialized")
    
    async def track_transaction(self, mempool_tx: MempoolTransaction) -> str:
        """Start tracking a pending transaction."""
        tracked_tx = TrackedTransaction(
            mempool_tx=mempool_tx,
            status=TransactionStatus.PENDING,
            submitted_time=datetime.now()
        )
        
        self._tracked_transactions[mempool_tx.tx_hash] = tracked_tx
        
        # Initialize chain metrics if needed
        if mempool_tx.chain not in self._metrics_by_chain:
            self._metrics_by_chain[mempool_tx.chain] = TransactionMetrics()
        
        self._metrics_by_chain[mempool_tx.chain].total_tracked += 1
        
        self.logger.debug(f"Started tracking transaction {mempool_tx.tx_hash[:10]}...")
        
        return mempool_tx.tx_hash
    
    async def update_transaction_status(self, 
                                      tx_hash: str, 
                                      status: TransactionStatus,
                                      block_number: Optional[int] = None,
                                      gas_used: Optional[int] = None,
                                      effective_gas_price: Optional[float] = None):
        """Update transaction status after confirmation/failure."""
        if tx_hash not in self._tracked_transactions:
            return
        
        tracked_tx = self._tracked_transactions[tx_hash]
        old_status = tracked_tx.status
        
        # Update status
        tracked_tx.status = status
        tracked_tx.block_number = block_number
        tracked_tx.gas_used = gas_used
        tracked_tx.effective_gas_price = effective_gas_price
        
        # Set confirmation time for final states
        if status in [TransactionStatus.CONFIRMED, TransactionStatus.FAILED]:
            tracked_tx.confirmed_time = datetime.now()
            tracked_tx.total_time_seconds = (
                tracked_tx.confirmed_time - tracked_tx.submitted_time
            ).total_seconds()
        
        # Update metrics
        chain = tracked_tx.mempool_tx.chain
        metrics = self._metrics_by_chain[chain]
        
        if status == TransactionStatus.CONFIRMED:
            metrics.confirmed += 1
        elif status == TransactionStatus.FAILED:
            metrics.failed += 1
        elif status == TransactionStatus.DROPPED:
            metrics.dropped += 1
        
        # Calculate derived metrics
        total_final = metrics.confirmed + metrics.failed + metrics.dropped
        if total_final > 0:
            metrics.success_rate = metrics.confirmed / total_final
        
        # Move to completed if final status
        if status in [TransactionStatus.CONFIRMED, TransactionStatus.FAILED, TransactionStatus.DROPPED]:
            self._completed_transactions.append(tracked_tx)
            del self._tracked_transactions[tx_hash]
            
            # Calculate averages
            self._update_average_metrics(chain)
        
        self.logger.info(f"Transaction {tx_hash[:10]}... status: {old_status.value} -> {status.value}")
    
    def _update_average_metrics(self, chain: ChainType):
        """Update average metrics for chain."""
        metrics = self._metrics_by_chain[chain]
        
        # Get recent completed transactions for this chain
        recent_cutoff = datetime.now() - timedelta(hours=self.max_tracking_hours)
        recent_confirmed = [
            tx for tx in self._completed_transactions
            if (tx.mempool_tx.chain == chain and 
                tx.status == TransactionStatus.CONFIRMED and
                tx.confirmed_time and tx.confirmed_time > recent_cutoff)
        ]
        
        if recent_confirmed:
            # Average confirmation time
            confirmation_times = [
                tx.total_time_seconds for tx in recent_confirmed
                if tx.total_time_seconds
            ]
            if confirmation_times:
                metrics.avg_confirmation_time = sum(confirmation_times) / len(confirmation_times)
            
            # Average gas used
            gas_used_values = [
                tx.gas_used for tx in recent_confirmed
                if tx.gas_used
            ]
            if gas_used_values:
                metrics.avg_gas_used = sum(gas_used_values) / len(gas_used_values)
            
            # Average slippage
            slippage_values = [
                tx.slippage_pct for tx in recent_confirmed
                if tx.slippage_pct is not None
            ]
            if slippage_values:
                metrics.avg_slippage = sum(slippage_values) / len(slippage_values)
    
    async def analyze_dex_transaction(self, tx_hash: str, actual_output: float):
        """Analyze DEX transaction for slippage and price impact."""
        if tx_hash not in self._tracked_transactions:
            return
        
        tracked_tx = self._tracked_transactions[tx_hash]
        mempool_tx = tracked_tx.mempool_tx
        
        # Calculate slippage if we have expected output
        if mempool_tx.amount_out_min and actual_output:
            expected_output = mempool_tx.amount_out_min
            slippage_pct = ((expected_output - actual_output) / expected_output) * 100
            tracked_tx.slippage_pct = slippage_pct
            tracked_tx.actual_amount_out = actual_output
            
            self.logger.info(f"Transaction {tx_hash[:10]}... slippage: {slippage_pct:.2f}%")
        
        # Calculate price impact (would need market data)
        # This is a simplified calculation
        if mempool_tx.amount_in and actual_output:
            # Price impact estimation (placeholder)
            trade_size_ratio = mempool_tx.amount_in / 100000  # Assume $100k reference
            estimated_impact = min(trade_size_ratio * 0.1, 5.0)  # Max 5% impact
            tracked_tx.price_impact_pct = estimated_impact
    
    def get_pending_transactions(self, chain: ChainType = None) -> List[TrackedTransaction]:
        """Get currently pending transactions."""
        pending = [tx for tx in self._tracked_transactions.values()]
        
        if chain:
            pending = [tx for tx in pending if tx.mempool_tx.chain == chain]
        
        return sorted(pending, key=lambda tx: tx.submitted_time, reverse=True)
    
    def get_recent_transactions(self, 
                              chain: ChainType = None, 
                              hours: int = 1,
                              status: TransactionStatus = None) -> List[TrackedTransaction]:
        """Get recent completed transactions."""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        recent = [
            tx for tx in self._completed_transactions
            if tx.confirmed_time and tx.confirmed_time > cutoff
        ]
        
        if chain:
            recent = [tx for tx in recent if tx.mempool_tx.chain == chain]
        
        if status:
            recent = [tx for tx in recent if tx.status == status]
        
        return sorted(recent, key=lambda tx: tx.confirmed_time or tx.submitted_time, reverse=True)
    
    def get_transaction_metrics(self, chain: ChainType = None) -> Dict[str, Any]:
        """Get transaction performance metrics."""
        if chain:
            if chain in self._metrics_by_chain:
                metrics = self._metrics_by_chain[chain]
                return {
                    "chain": chain.value,
                    "total_tracked": metrics.total_tracked,
                    "confirmed": metrics.confirmed,
                    "failed": metrics.failed,
                    "dropped": metrics.dropped,
                    "success_rate": metrics.success_rate,
                    "avg_confirmation_time": metrics.avg_confirmation_time,
                    "avg_gas_used": metrics.avg_gas_used,
                    "avg_slippage": metrics.avg_slippage
                }
            else:
                return {"chain": chain.value, "no_data": True}
        else:
            # Aggregate all chains
            return {
                chain.value: self.get_transaction_metrics(chain)
                for chain in self._metrics_by_chain.keys()
            }
    
    def get_failed_transaction_analysis(self, chain: ChainType = None) -> Dict[str, Any]:
        """Analyze failed transactions to identify common issues."""
        failed_txs = self.get_recent_transactions(
            chain=chain, 
            hours=24, 
            status=TransactionStatus.FAILED
        )
        
        if not failed_txs:
            return {"no_failures": True}
        
        # Analyze failure patterns
        gas_price_failures = []
        timeout_failures = []
        slippage_failures = []
        
        for tx in failed_txs:
            # Check if gas price was too low
            if tx.mempool_tx.gas_price < 10:  # Arbitrary threshold
                gas_price_failures.append(tx)
            
            # Check if transaction timed out
            if tx.total_time_seconds and tx.total_time_seconds > 300:  # 5 minutes
                timeout_failures.append(tx)
            
            # Check for high slippage (if DEX transaction)
            if tx.slippage_pct and tx.slippage_pct > 5.0:  # 5% threshold
                slippage_failures.append(tx)
        
        return {
            "total_failures": len(failed_txs),
            "gas_price_failures": len(gas_price_failures),
            "timeout_failures": len(timeout_failures),
            "slippage_failures": len(slippage_failures),
            "failure_rate": len(failed_txs) / max(1, len(self._completed_transactions)),
            "common_issues": [
                "Low gas price" if gas_price_failures else None,
                "Transaction timeout" if timeout_failures else None,
                "High slippage" if slippage_failures else None
            ]
        }
    
    def cleanup_old_data(self):
        """Clean up old transaction data."""
        cutoff = datetime.now() - timedelta(hours=self.max_tracking_hours)
        
        # Clean completed transactions
        self._completed_transactions = [
            tx for tx in self._completed_transactions
            if tx.confirmed_time and tx.confirmed_time > cutoff
        ]
        
        # Check for timed out pending transactions
        timed_out = []
        for tx_hash, tx in self._tracked_transactions.items():
            timeout = self._confirmation_timeouts.get(tx.mempool_tx.chain, 300)
            if (datetime.now() - tx.submitted_time).total_seconds() > timeout:
                timed_out.append(tx_hash)
        
        # Mark timed out transactions as dropped
        for tx_hash in timed_out:
            asyncio.create_task(
                self.update_transaction_status(tx_hash, TransactionStatus.DROPPED)
            )
        
        self.logger.debug(f"Cleaned up {len(timed_out)} timed out transactions")
    
    def get_transaction_by_hash(self, tx_hash: str) -> Optional[TrackedTransaction]:
        """Get transaction by hash."""
        # Check pending first
        if tx_hash in self._tracked_transactions:
            return self._tracked_transactions[tx_hash]
        
        # Check completed
        for tx in self._completed_transactions:
            if tx.mempool_tx.tx_hash == tx_hash:
                return tx
        
        return None