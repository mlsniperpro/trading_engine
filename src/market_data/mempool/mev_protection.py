"""
MEV Protection

Detects and protects against MEV (Maximal Extractable Value) attacks:
- Front-running detection
- Sandwich attack identification
- Back-running analysis
- Protection strategies
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging

from src.market_data.mempool.mempool_monitor import MempoolTransaction, ChainType


class MEVAttackType(Enum):
    """Types of MEV attacks."""
    FRONT_RUNNING = "FRONT_RUNNING"
    SANDWICH_ATTACK = "SANDWICH_ATTACK"
    BACK_RUNNING = "BACK_RUNNING"
    ARBITRAGE = "ARBITRAGE"
    LIQUIDATION = "LIQUIDATION"


@dataclass
class MEVThreat:
    """MEV threat detection result."""
    attack_type: MEVAttackType
    confidence: float  # 0.0 to 1.0
    victim_tx: MempoolTransaction
    attacker_txs: List[MempoolTransaction]
    estimated_profit: Optional[float] = None
    protection_strategy: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class ProtectionConfig:
    """MEV protection configuration."""
    enable_detection: bool = True
    min_confidence_threshold: float = 0.7
    max_gas_price_multiplier: float = 1.5
    enable_private_mempool: bool = False
    delay_submission: bool = True
    randomize_timing: bool = True


class MEVProtector:
    """
    MEV protection and detection system.
    
    Features:
    - Real-time MEV attack detection
    - Transaction protection strategies
    - Gas price optimization
    - Private mempool routing
    """
    
    def __init__(self, config: ProtectionConfig = None):
        self.config = config or ProtectionConfig()
        self.logger = logging.getLogger(__name__)
        
        # Attack detection state
        self._recent_transactions: Dict[str, List[MempoolTransaction]] = {}  # pool -> txs
        self._detected_threats: List[MEVThreat] = []
        self._known_mev_bots: set = set()
        
        # Protection metrics
        self._attacks_detected = 0
        self._attacks_prevented = 0
        self._gas_saved = 0.0
        
        # MEV bot patterns (simplified)
        self._suspicious_patterns = {
            "high_gas_price": 100.0,  # Gwei
            "duplicate_function_calls": True,
            "similar_amounts": True,
            "rapid_submission": 1.0  # seconds
        }
        
        self.logger.info("MEV Protector initialized")
    
    async def analyze_transaction(self, tx: MempoolTransaction) -> Dict[str, Any]:
        """
        Analyze transaction for MEV threats.
        
        Returns analysis result with threat assessment.
        """
        try:
            # Store transaction for pattern analysis
            pool_key = f"{tx.chain.value}_{tx.to_address}"
            if pool_key not in self._recent_transactions:
                self._recent_transactions[pool_key] = []
            
            self._recent_transactions[pool_key].append(tx)
            
            # Keep only recent transactions
            cutoff = datetime.now() - timedelta(minutes=5)
            self._recent_transactions[pool_key] = [
                t for t in self._recent_transactions[pool_key]
                if t.timestamp > cutoff
            ]
            
            # Detect different types of MEV attacks
            threats = []
            
            # Front-running detection
            front_run_threat = await self._detect_front_running(tx)
            if front_run_threat:
                threats.append(front_run_threat)
            
            # Sandwich attack detection
            sandwich_threat = await self._detect_sandwich_attack(tx)
            if sandwich_threat:
                threats.append(sandwich_threat)
            
            # Back-running detection
            back_run_threat = await self._detect_back_running(tx)
            if back_run_threat:
                threats.append(back_run_threat)
            
            # Store detected threats
            for threat in threats:
                if threat.confidence >= self.config.min_confidence_threshold:
                    self._detected_threats.append(threat)
                    self._attacks_detected += 1
            
            # Clean up old threats
            self._cleanup_old_threats()
            
            # Generate analysis result
            is_mev_attack = len(threats) > 0
            max_confidence = max([t.confidence for t in threats], default=0.0)
            
            return {
                "is_mev_attack": is_mev_attack,
                "confidence": max_confidence,
                "threat_types": [t.attack_type.value for t in threats],
                "threats_detected": len(threats),
                "protection_recommended": max_confidence >= self.config.min_confidence_threshold
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing transaction for MEV: {e}")
            return {"error": str(e), "is_mev_attack": False}
    
    async def _detect_front_running(self, tx: MempoolTransaction) -> Optional[MEVThreat]:
        """Detect front-running attacks."""
        pool_key = f"{tx.chain.value}_{tx.to_address}"
        recent_txs = self._recent_transactions.get(pool_key, [])
        
        if len(recent_txs) < 2:
            return None
        
        # Look for transactions with similar function calls but higher gas
        suspicious_txs = []
        
        for other_tx in recent_txs[:-1]:  # Exclude current tx
            # Check for higher gas price (front-running indicator)
            if (other_tx.gas_price > tx.gas_price * 1.1 and
                other_tx.timestamp > tx.timestamp - timedelta(seconds=10)):
                
                # Check for similar transaction data (same function call)
                if self._similar_function_calls(tx.data, other_tx.data):
                    suspicious_txs.append(other_tx)
        
        if suspicious_txs:
            confidence = min(0.9, len(suspicious_txs) * 0.3 + 0.4)
            
            return MEVThreat(
                attack_type=MEVAttackType.FRONT_RUNNING,
                confidence=confidence,
                victim_tx=tx,
                attacker_txs=suspicious_txs,
                protection_strategy="increase_gas_price"
            )
        
        return None
    
    async def _detect_sandwich_attack(self, tx: MempoolTransaction) -> Optional[MEVThreat]:
        """Detect sandwich attacks."""
        pool_key = f"{tx.chain.value}_{tx.to_address}"
        recent_txs = self._recent_transactions.get(pool_key, [])
        
        if len(recent_txs) < 3:
            return None
        
        # Look for sandwich pattern: buy -> victim trade -> sell
        # This is a simplified detection
        
        # Find potential front-run transaction (higher gas, similar timing)
        front_tx = None
        back_tx = None
        
        for other_tx in recent_txs:
            if other_tx == tx:
                continue
            
            # Potential front-run (higher gas, before victim)
            if (other_tx.gas_price > tx.gas_price * 1.05 and
                other_tx.timestamp < tx.timestamp and
                (tx.timestamp - other_tx.timestamp).total_seconds() < 30):
                front_tx = other_tx
            
            # Potential back-run (after victim, might be lower gas)
            if (other_tx.timestamp > tx.timestamp and
                (other_tx.timestamp - tx.timestamp).total_seconds() < 30 and
                other_tx.from_address == (front_tx.from_address if front_tx else "")):
                back_tx = other_tx
        
        if front_tx and back_tx:
            # Check if it's the same address (sandwich pattern)
            if front_tx.from_address == back_tx.from_address:
                confidence = 0.8
                
                # Estimate profit (simplified)
                estimated_profit = self._estimate_sandwich_profit(front_tx, tx, back_tx)
                
                return MEVThreat(
                    attack_type=MEVAttackType.SANDWICH_ATTACK,
                    confidence=confidence,
                    victim_tx=tx,
                    attacker_txs=[front_tx, back_tx],
                    estimated_profit=estimated_profit,
                    protection_strategy="split_order_or_delay"
                )
        
        return None
    
    async def _detect_back_running(self, tx: MempoolTransaction) -> Optional[MEVThreat]:
        """Detect back-running attacks."""
        pool_key = f"{tx.chain.value}_{tx.to_address}"
        recent_txs = self._recent_transactions.get(pool_key, [])
        
        # Look for transactions that follow quickly with arbitrage patterns
        following_txs = []
        
        for other_tx in recent_txs:
            if (other_tx.timestamp > tx.timestamp and
                (other_tx.timestamp - tx.timestamp).total_seconds() < 10):
                
                # Check if it's likely an arbitrage transaction
                if self._is_arbitrage_pattern(other_tx):
                    following_txs.append(other_tx)
        
        if following_txs:
            confidence = 0.6  # Back-running is less harmful than front-running
            
            return MEVThreat(
                attack_type=MEVAttackType.BACK_RUNNING,
                confidence=confidence,
                victim_tx=tx,
                attacker_txs=following_txs,
                protection_strategy="none_required"
            )
        
        return None
    
    def _similar_function_calls(self, data1: str, data2: str) -> bool:
        """Check if two transaction data contain similar function calls."""
        if len(data1) < 10 or len(data2) < 10:
            return False
        
        # Compare function selectors (first 4 bytes after 0x)
        if len(data1) >= 10 and len(data2) >= 10:
            selector1 = data1[:10]  # 0x + 8 hex chars
            selector2 = data2[:10]
            return selector1 == selector2
        
        return False
    
    def _is_arbitrage_pattern(self, tx: MempoolTransaction) -> bool:
        """Detect if transaction matches arbitrage patterns."""
        # Simplified arbitrage detection
        # Real implementation would decode transaction data
        
        # High gas price (willing to pay for priority)
        if tx.gas_price > self._suspicious_patterns["high_gas_price"]:
            return True
        
        # Large transaction value (typical for arbitrage)
        if tx.value > 50000:  # $50k+
            return True
        
        return False
    
    def _estimate_sandwich_profit(self, 
                                front_tx: MempoolTransaction,
                                victim_tx: MempoolTransaction,
                                back_tx: MempoolTransaction) -> float:
        """Estimate profit from sandwich attack."""
        # Simplified profit estimation
        # Real implementation would simulate the trades
        
        # Estimate based on trade size and slippage
        victim_size = victim_tx.value
        estimated_slippage = min(victim_size / 100000 * 0.5, 5.0)  # Max 5%
        estimated_profit = victim_size * (estimated_slippage / 100)
        
        return estimated_profit
    
    def _cleanup_old_threats(self):
        """Clean up old threat data."""
        cutoff = datetime.now() - timedelta(hours=1)
        self._detected_threats = [
            threat for threat in self._detected_threats
            if threat.timestamp > cutoff
        ]
        
        # Clean up transaction history
        for pool_key in list(self._recent_transactions.keys()):
            self._recent_transactions[pool_key] = [
                tx for tx in self._recent_transactions[pool_key]
                if tx.timestamp > cutoff
            ]
    
    def get_protection_strategy(self, tx: MempoolTransaction) -> Dict[str, Any]:
        """Get protection strategy for a transaction."""
        # Analyze current threats
        analysis = await self.analyze_transaction(tx)
        
        if not analysis.get("is_mev_attack"):
            return {"strategy": "none", "confidence": 0.0}
        
        strategy = {
            "strategy": "standard_protection",
            "confidence": analysis["confidence"],
            "recommendations": []
        }
        
        # High confidence threats need strong protection
        if analysis["confidence"] > 0.8:
            strategy["recommendations"].extend([
                "Increase gas price by 20-50%",
                "Use private mempool if available",
                "Add random delay (1-5 seconds)",
                "Consider splitting large orders"
            ])
        elif analysis["confidence"] > 0.6:
            strategy["recommendations"].extend([
                "Increase gas price by 10-20%",
                "Add small random delay",
                "Monitor for confirmation"
            ])
        else:
            strategy["recommendations"].append("Standard gas price acceptable")
        
        return strategy
    
    def get_threat_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get summary of recent MEV threats."""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_threats = [
            threat for threat in self._detected_threats
            if threat.timestamp > cutoff
        ]
        
        if not recent_threats:
            return {"no_threats": True, "period_hours": hours}
        
        # Group by attack type
        threats_by_type = {}
        total_estimated_profit = 0.0
        
        for threat in recent_threats:
            attack_type = threat.attack_type.value
            if attack_type not in threats_by_type:
                threats_by_type[attack_type] = 0
            threats_by_type[attack_type] += 1
            
            if threat.estimated_profit:
                total_estimated_profit += threat.estimated_profit
        
        return {
            "total_threats": len(recent_threats),
            "threats_by_type": threats_by_type,
            "avg_confidence": sum(t.confidence for t in recent_threats) / len(recent_threats),
            "total_estimated_profit": total_estimated_profit,
            "period_hours": hours,
            "most_common_attack": max(threats_by_type.keys(), key=threats_by_type.get) if threats_by_type else None
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get MEV protection statistics."""
        return {
            "attacks_detected": self._attacks_detected,
            "attacks_prevented": self._attacks_prevented,
            "detection_rate": len(self._detected_threats),
            "known_mev_bots": len(self._known_mev_bots),
            "protection_enabled": self.config.enable_detection,
            "confidence_threshold": self.config.min_confidence_threshold
        }