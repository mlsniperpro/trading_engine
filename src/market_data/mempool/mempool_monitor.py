"""
Mempool Monitor

Monitors pending transactions in blockchain mempools for:
- MEV protection and detection
- Large transaction tracking
- Gas price trends
- Pending arbitrage opportunities

Critical for DEX trading on EVM chains.
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import logging
import json

from src.core.base import Component as BaseComponent
from src.core.events import Event
from src.market_data.mempool.transaction_tracker import TransactionTracker
from src.market_data.mempool.gas_oracle import GasOracle
from src.market_data.mempool.mev_protection import MEVProtector


class ChainType(Enum):
    """Supported blockchain types."""
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    BSC = "bsc"


@dataclass
class MempoolTransaction:
    """Pending transaction data."""
    tx_hash: str
    from_address: str
    to_address: str
    value: float
    gas_price: float
    gas_limit: int
    data: str
    timestamp: datetime
    chain: ChainType
    
    # DEX-specific fields
    dex_router: Optional[str] = None
    token_in: Optional[str] = None
    token_out: Optional[str] = None
    amount_in: Optional[float] = None
    amount_out_min: Optional[float] = None
    deadline: Optional[int] = None


@dataclass
class MempoolAlert:
    """Mempool-based alert."""
    alert_type: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    message: str
    transaction: MempoolTransaction
    metadata: Dict[str, Any]
    timestamp: datetime


class MempoolMonitor(BaseComponent):
    """
    Core mempool monitoring system.
    
    Responsibilities:
    1. Connect to mempool data sources
    2. Filter relevant transactions
    3. Detect MEV opportunities/threats
    4. Track large trades and arbitrage
    5. Monitor gas prices
    """
    
    def __init__(self, 
                 chains: List[ChainType],
                 min_value_threshold: float = 10000.0,  # $10k minimum
                 gas_price_alerts: bool = True,
                 mev_protection: bool = True):
        super().__init__()
        self.chains = chains
        self.min_value_threshold = min_value_threshold
        self.gas_price_alerts = gas_price_alerts
        self.mev_protection_enabled = mev_protection
        
        self.logger = logging.getLogger(__name__)
        
        # Components
        self.transaction_tracker = TransactionTracker()
        self.gas_oracle = GasOracle()
        self.mev_protector = MEVProtector() if mev_protection else None
        
        # State tracking
        self._pending_transactions = {}  # tx_hash -> MempoolTransaction
        self._large_transactions = []    # Recent large transactions
        self._gas_price_history = {}    # chain -> price history
        self._alert_callbacks = []      # Alert handlers
        
        # Monitoring configuration
        self._dex_routers = {
            ChainType.ETHEREUM: [
                "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",  # Uniswap V2
                "0xe592427a0aece92de3edee1f18e0157c05861564",  # Uniswap V3
                "0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f",  # Sushiswap
            ],
            # Add other chains as needed
        }
        
        # Performance metrics
        self._transactions_processed = 0
        self._alerts_generated = 0
        self._mev_attacks_detected = 0
        
        self.logger.info(f"MempoolMonitor initialized for chains: {[c.value for c in chains]}")
    
    async def start_monitoring(self):
        """Start monitoring mempool for all configured chains."""
        monitoring_tasks = []
        
        for chain in self.chains:
            task = asyncio.create_task(self._monitor_chain(chain))
            monitoring_tasks.append(task)
        
        # Start gas oracle
        if self.gas_price_alerts:
            gas_task = asyncio.create_task(self.gas_oracle.start_monitoring(self.chains))
            monitoring_tasks.append(gas_task)
        
        # Wait for all tasks
        await asyncio.gather(*monitoring_tasks, return_exceptions=True)
    
    async def _monitor_chain(self, chain: ChainType):
        """Monitor mempool for specific chain."""
        try:
            # Connect to chain's mempool feed
            # This would connect to services like:
            # - Ethereum: Alchemy/Infura pending tx stream
            # - Polygon: QuickNode mempool
            # - etc.
            
            self.logger.info(f"Starting mempool monitoring for {chain.value}")
            
            # Simulate mempool connection
            while True:
                try:
                    # In real implementation, this would receive actual mempool data
                    await self._simulate_mempool_data(chain)
                    await asyncio.sleep(1)  # Adjust based on chain block time
                    
                except Exception as e:
                    self.logger.error(f"Error monitoring {chain.value} mempool: {e}")
                    await asyncio.sleep(5)  # Wait before retry
                    
        except Exception as e:
            self.logger.error(f"Fatal error in {chain.value} monitoring: {e}")
    
    async def _simulate_mempool_data(self, chain: ChainType):
        """Simulate mempool data for testing."""
        # This is a placeholder - replace with actual mempool connection
        import random
        
        # Generate random transaction for testing
        if random.random() < 0.1:  # 10% chance of generating a transaction
            tx = MempoolTransaction(
                tx_hash=f"0x{''.join(random.choices('0123456789abcdef', k=64))}",
                from_address=f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
                to_address=random.choice(self._dex_routers.get(chain, ["0x" + "0" * 40])),
                value=random.uniform(1000, 50000),
                gas_price=random.uniform(10, 100),
                gas_limit=random.randint(200000, 500000),
                data="0x" + "".join(random.choices('0123456789abcdef', k=128)),
                timestamp=datetime.now(),
                chain=chain
            )
            
            await self._process_transaction(tx)
    
    async def _process_transaction(self, tx: MempoolTransaction):
        """Process a pending transaction."""
        try:
            self._transactions_processed += 1
            
            # Store transaction
            self._pending_transactions[tx.tx_hash] = tx
            
            # Check if it's a DEX transaction
            if self._is_dex_transaction(tx):
                decoded_tx = await self._decode_dex_transaction(tx)
                if decoded_tx:
                    tx = decoded_tx
            
            # Apply filters
            if not self._should_monitor_transaction(tx):
                return
            
            # Track large transactions
            if tx.value >= self.min_value_threshold:
                self._large_transactions.append(tx)
                await self._alert_large_transaction(tx)
            
            # MEV protection
            if self.mev_protector:
                mev_analysis = await self.mev_protector.analyze_transaction(tx)
                if mev_analysis.get('is_mev_attack'):
                    await self._alert_mev_attack(tx, mev_analysis)
            
            # Update transaction tracker
            await self.transaction_tracker.track_transaction(tx)
            
            # Clean up old transactions
            self._cleanup_old_transactions()
            
        except Exception as e:
            self.logger.error(f"Error processing transaction {tx.tx_hash}: {e}")
    
    def _is_dex_transaction(self, tx: MempoolTransaction) -> bool:
        """Check if transaction is a DEX trade."""
        dex_routers = self._dex_routers.get(tx.chain, [])
        return tx.to_address.lower() in [router.lower() for router in dex_routers]
    
    async def _decode_dex_transaction(self, tx: MempoolTransaction) -> Optional[MempoolTransaction]:
        """Decode DEX transaction data."""
        try:
            # This would use libraries like web3.py to decode transaction data
            # For now, simulate basic decoding
            
            if "swap" in tx.data.lower():
                # Simulate swap decoding
                tx.token_in = "0xA0b86a33E6441949620B"  # Example token address
                tx.token_out = "0xC02aaA39b223FE8D0A0e"  # Example WETH address
                tx.amount_in = tx.value
                tx.amount_out_min = tx.value * 0.95  # Assume 5% slippage tolerance
                tx.deadline = int(datetime.now().timestamp()) + 1800  # 30 minutes
                tx.dex_router = tx.to_address
            
            return tx
            
        except Exception as e:
            self.logger.error(f"Error decoding DEX transaction: {e}")
            return None
    
    def _should_monitor_transaction(self, tx: MempoolTransaction) -> bool:
        """Check if transaction should be monitored."""
        # Value threshold
        if tx.value < self.min_value_threshold:
            return False
        
        # Only monitor DEX transactions for now
        if not self._is_dex_transaction(tx):
            return False
        
        return True
    
    async def _alert_large_transaction(self, tx: MempoolTransaction):
        """Generate alert for large transaction."""
        alert = MempoolAlert(
            alert_type="LARGE_TRANSACTION",
            severity="HIGH" if tx.value >= 100000 else "MEDIUM",
            message=f"Large {tx.chain.value} transaction detected: ${tx.value:,.2f}",
            transaction=tx,
            metadata={
                "value_usd": tx.value,
                "gas_price": tx.gas_price,
                "is_dex": self._is_dex_transaction(tx)
            },
            timestamp=datetime.now()
        )
        
        await self._emit_alert(alert)
    
    async def _alert_mev_attack(self, tx: MempoolTransaction, mev_analysis: Dict[str, Any]):
        """Generate alert for potential MEV attack."""
        self._mev_attacks_detected += 1
        
        alert = MempoolAlert(
            alert_type="MEV_ATTACK",
            severity="CRITICAL",
            message=f"Potential MEV attack detected on {tx.chain.value}",
            transaction=tx,
            metadata=mev_analysis,
            timestamp=datetime.now()
        )
        
        await self._emit_alert(alert)
    
    async def _emit_alert(self, alert: MempoolAlert):
        """Emit alert to all registered callbacks."""
        self._alerts_generated += 1
        
        self.logger.warning(f"Mempool Alert [{alert.severity}]: {alert.message}")
        
        for callback in self._alert_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                self.logger.error(f"Error in alert callback: {e}")
    
    def _cleanup_old_transactions(self):
        """Clean up old pending transactions."""
        cutoff = datetime.now() - timedelta(minutes=30)
        
        # Clean pending transactions
        old_hashes = [
            tx_hash for tx_hash, tx in self._pending_transactions.items()
            if tx.timestamp < cutoff
        ]
        
        for tx_hash in old_hashes:
            del self._pending_transactions[tx_hash]
        
        # Clean large transactions
        self._large_transactions = [
            tx for tx in self._large_transactions
            if tx.timestamp > cutoff
        ]
    
    def add_alert_callback(self, callback: Callable[[MempoolAlert], None]):
        """Add callback for mempool alerts."""
        self._alert_callbacks.append(callback)
    
    def get_pending_transactions(self, chain: ChainType = None, min_value: float = None) -> List[MempoolTransaction]:
        """Get current pending transactions."""
        transactions = list(self._pending_transactions.values())
        
        if chain:
            transactions = [tx for tx in transactions if tx.chain == chain]
        
        if min_value:
            transactions = [tx for tx in transactions if tx.value >= min_value]
        
        return sorted(transactions, key=lambda tx: tx.value, reverse=True)
    
    def get_large_transactions(self, hours: int = 1) -> List[MempoolTransaction]:
        """Get recent large transactions."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [tx for tx in self._large_transactions if tx.timestamp > cutoff]
    
    def get_gas_prices(self, chain: ChainType) -> Dict[str, float]:
        """Get current gas prices for chain."""
        return self.gas_oracle.get_gas_prices(chain)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        return {
            "transactions_processed": self._transactions_processed,
            "alerts_generated": self._alerts_generated,
            "mev_attacks_detected": self._mev_attacks_detected,
            "pending_transactions": len(self._pending_transactions),
            "large_transactions_1h": len(self.get_large_transactions(1)),
            "monitored_chains": [chain.value for chain in self.chains],
            "uptime": "Active"  # Would track actual uptime
        }
    
    async def stop_monitoring(self):
        """Stop mempool monitoring."""
        self.logger.info("Stopping mempool monitoring")
        # Clean shutdown logic here