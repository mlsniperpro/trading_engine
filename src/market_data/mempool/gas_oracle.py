"""
Gas Oracle

Tracks and predicts gas prices across chains for:
- Optimal transaction timing
- Cost estimation
- Network congestion detection
- MEV auction insights
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import logging
import statistics

from src.market_data.mempool.mempool_monitor import ChainType


@dataclass
class GasPrice:
    """Gas price data point."""
    chain: ChainType
    slow: float      # Gwei - for non-urgent transactions
    standard: float  # Gwei - for normal transactions  
    fast: float      # Gwei - for urgent transactions
    instant: float   # Gwei - for immediate confirmation
    timestamp: datetime
    block_number: Optional[int] = None


@dataclass
class GasPrediction:
    """Gas price prediction."""
    chain: ChainType
    predicted_price: float
    confidence: float  # 0.0 to 1.0
    timeframe_minutes: int
    factors: List[str]  # Factors influencing prediction
    timestamp: datetime


class NetworkCongestion(Enum):
    """Network congestion levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class GasOracle:
    """
    Gas price oracle and prediction system.
    
    Features:
    - Real-time gas price tracking
    - Historical analysis
    - Congestion detection
    - Price predictions
    - Multi-chain support
    """
    
    def __init__(self, 
                 history_hours: int = 24,
                 prediction_models: bool = True):
        self.history_hours = history_hours
        self.prediction_models = prediction_models
        self.logger = logging.getLogger(__name__)
        
        # Gas price storage
        self._gas_history: Dict[ChainType, List[GasPrice]] = {}
        self._current_prices: Dict[ChainType, GasPrice] = {}
        self._predictions: Dict[ChainType, List[GasPrediction]] = {}
        
        # Network state tracking
        self._congestion_levels: Dict[ChainType, NetworkCongestion] = {}
        self._block_times: Dict[ChainType, List[float]] = {}
        
        # API endpoints for gas data (would be real endpoints)
        self._gas_apis = {
            ChainType.ETHEREUM: "https://api.etherscan.io/api",
            ChainType.POLYGON: "https://api.polygonscan.com/api",
            ChainType.ARBITRUM: "https://api.arbiscan.io/api",
            ChainType.OPTIMISM: "https://api-optimistic.etherscan.io/api",
            ChainType.BSC: "https://api.bscscan.com/api"
        }
        
        self.logger.info("Gas Oracle initialized")
    
    async def start_monitoring(self, chains: List[ChainType]):
        """Start gas price monitoring for specified chains."""
        monitoring_tasks = []
        
        for chain in chains:
            # Initialize history storage
            self._gas_history[chain] = []
            self._block_times[chain] = []
            self._predictions[chain] = []
            self._congestion_levels[chain] = NetworkCongestion.LOW
            
            # Start monitoring task
            task = asyncio.create_task(self._monitor_gas_prices(chain))
            monitoring_tasks.append(task)
        
        # Start prediction task
        if self.prediction_models:
            pred_task = asyncio.create_task(self._generate_predictions())
            monitoring_tasks.append(pred_task)
        
        await asyncio.gather(*monitoring_tasks, return_exceptions=True)
    
    async def _monitor_gas_prices(self, chain: ChainType):
        """Monitor gas prices for a specific chain."""
        while True:
            try:
                gas_price = await self._fetch_gas_prices(chain)
                if gas_price:
                    await self._process_gas_price(gas_price)
                
                # Fetch interval based on chain
                interval = self._get_fetch_interval(chain)
                await asyncio.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"Error monitoring gas prices for {chain.value}: {e}")
                await asyncio.sleep(30)  # Wait before retry
    
    async def _fetch_gas_prices(self, chain: ChainType) -> Optional[GasPrice]:
        """Fetch current gas prices from APIs."""
        try:
            # This would make actual API calls to gas price services
            # For now, simulate gas prices
            
            import random
            base_price = {
                ChainType.ETHEREUM: 20.0,
                ChainType.POLYGON: 30.0,
                ChainType.ARBITRUM: 0.1,
                ChainType.OPTIMISM: 0.1,
                ChainType.BSC: 5.0
            }.get(chain, 20.0)
            
            # Add some randomness to simulate real fluctuations
            multiplier = random.uniform(0.8, 1.5)
            
            return GasPrice(
                chain=chain,
                slow=base_price * multiplier * 0.8,
                standard=base_price * multiplier,
                fast=base_price * multiplier * 1.3,
                instant=base_price * multiplier * 1.8,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error fetching gas prices for {chain.value}: {e}")
            return None
    
    def _get_fetch_interval(self, chain: ChainType) -> int:
        """Get appropriate fetch interval for chain."""
        # Faster chains need more frequent updates
        intervals = {
            ChainType.ETHEREUM: 15,    # 15 seconds
            ChainType.POLYGON: 5,      # 5 seconds
            ChainType.ARBITRUM: 10,    # 10 seconds
            ChainType.OPTIMISM: 10,    # 10 seconds  
            ChainType.BSC: 5           # 5 seconds
        }
        return intervals.get(chain, 15)
    
    async def _process_gas_price(self, gas_price: GasPrice):
        """Process new gas price data."""
        chain = gas_price.chain
        
        # Store current price
        self._current_prices[chain] = gas_price
        
        # Add to history
        self._gas_history[chain].append(gas_price)
        
        # Cleanup old history
        cutoff = datetime.now() - timedelta(hours=self.history_hours)
        self._gas_history[chain] = [
            gp for gp in self._gas_history[chain]
            if gp.timestamp > cutoff
        ]
        
        # Update congestion level
        self._update_congestion_level(chain)
        
        # Log significant changes
        self._log_price_changes(gas_price)
    
    def _update_congestion_level(self, chain: ChainType):
        """Update network congestion level based on gas prices."""
        history = self._gas_history[chain]
        
        if len(history) < 10:
            return
        
        # Calculate recent average
        recent_prices = [gp.standard for gp in history[-10:]]
        current_price = history[-1].standard
        avg_price = statistics.mean(recent_prices)
        
        # Determine congestion level
        if current_price > avg_price * 2.0:
            level = NetworkCongestion.CRITICAL
        elif current_price > avg_price * 1.5:
            level = NetworkCongestion.HIGH
        elif current_price > avg_price * 1.2:
            level = NetworkCongestion.MEDIUM
        else:
            level = NetworkCongestion.LOW
        
        # Update if changed
        old_level = self._congestion_levels.get(chain)
        if old_level != level:
            self._congestion_levels[chain] = level
            self.logger.info(f"{chain.value} congestion level changed: {old_level} -> {level.value}")
    
    def _log_price_changes(self, gas_price: GasPrice):
        """Log significant gas price changes."""
        chain = gas_price.chain
        history = self._gas_history[chain]
        
        if len(history) < 2:
            return
        
        previous_price = history[-2].standard
        current_price = gas_price.standard
        
        change_pct = ((current_price - previous_price) / previous_price) * 100
        
        # Log significant changes
        if abs(change_pct) > 20:  # 20% change
            direction = "increased" if change_pct > 0 else "decreased"
            self.logger.info(
                f"{chain.value} gas price {direction} {abs(change_pct):.1f}%: "
                f"{previous_price:.2f} -> {current_price:.2f} gwei"
            )
    
    async def _generate_predictions(self):
        """Generate gas price predictions."""
        while True:
            try:
                for chain in self._gas_history.keys():
                    prediction = await self._predict_gas_price(chain)
                    if prediction:
                        self._predictions[chain].append(prediction)
                        
                        # Keep only recent predictions
                        cutoff = datetime.now() - timedelta(hours=2)
                        self._predictions[chain] = [
                            p for p in self._predictions[chain]
                            if p.timestamp > cutoff
                        ]
                
                await asyncio.sleep(300)  # Generate predictions every 5 minutes
                
            except Exception as e:
                self.logger.error(f"Error generating predictions: {e}")
                await asyncio.sleep(60)
    
    async def _predict_gas_price(self, chain: ChainType) -> Optional[GasPrediction]:
        """Generate gas price prediction for chain."""
        history = self._gas_history[chain]
        
        if len(history) < 20:  # Need sufficient history
            return None
        
        try:
            # Simple prediction based on trends and patterns
            recent_prices = [gp.standard for gp in history[-20:]]
            current_price = recent_prices[-1]
            
            # Calculate trend
            trend_prices = [gp.standard for gp in history[-10:]]
            trend = statistics.mean(trend_prices[-5:]) - statistics.mean(trend_prices[:5])
            
            # Calculate volatility
            volatility = statistics.stdev(recent_prices)
            
            # Simple prediction: current price + trend, bounded by volatility
            predicted_price = current_price + (trend * 0.5)
            
            # Adjust for congestion
            congestion = self._congestion_levels[chain]
            if congestion == NetworkCongestion.CRITICAL:
                predicted_price *= 1.2
            elif congestion == NetworkCongestion.HIGH:
                predicted_price *= 1.1
            
            # Calculate confidence based on volatility
            confidence = max(0.3, min(0.9, 1.0 - (volatility / current_price)))
            
            # Identify factors
            factors = []
            if abs(trend) > current_price * 0.1:
                factors.append("Strong trend")
            if congestion in [NetworkCongestion.HIGH, NetworkCongestion.CRITICAL]:
                factors.append("Network congestion")
            if volatility > current_price * 0.3:
                factors.append("High volatility")
            
            return GasPrediction(
                chain=chain,
                predicted_price=max(0, predicted_price),
                confidence=confidence,
                timeframe_minutes=15,
                factors=factors,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error predicting gas price for {chain.value}: {e}")
            return None
    
    def get_gas_prices(self, chain: ChainType) -> Dict[str, float]:
        """Get current gas prices for chain."""
        current = self._current_prices.get(chain)
        
        if not current:
            return {}
        
        return {
            "slow": current.slow,
            "standard": current.standard,
            "fast": current.fast,
            "instant": current.instant,
            "timestamp": current.timestamp.isoformat()
        }
    
    def get_congestion_level(self, chain: ChainType) -> NetworkCongestion:
        """Get current congestion level for chain."""
        return self._congestion_levels.get(chain, NetworkCongestion.LOW)
    
    def get_price_history(self, chain: ChainType, hours: int = 1) -> List[GasPrice]:
        """Get gas price history for chain."""
        cutoff = datetime.now() - timedelta(hours=hours)
        history = self._gas_history.get(chain, [])
        
        return [gp for gp in history if gp.timestamp > cutoff]
    
    def get_prediction(self, chain: ChainType, minutes_ahead: int = 15) -> Optional[GasPrediction]:
        """Get gas price prediction for specified time ahead."""
        predictions = self._predictions.get(chain, [])
        
        if not predictions:
            return None
        
        # Find prediction closest to requested timeframe
        target_predictions = [
            p for p in predictions 
            if abs(p.timeframe_minutes - minutes_ahead) <= 5
        ]
        
        if target_predictions:
            # Return most recent prediction
            return max(target_predictions, key=lambda p: p.timestamp)
        
        return None
    
    def estimate_transaction_cost(self, 
                                chain: ChainType, 
                                gas_limit: int, 
                                speed: str = "standard") -> Dict[str, float]:
        """Estimate transaction cost in ETH and USD."""
        gas_prices = self.get_gas_prices(chain)
        
        if not gas_prices:
            return {}
        
        gas_price = gas_prices.get(speed, gas_prices.get("standard", 0))
        
        # Convert gwei to ETH
        cost_eth = (gas_price * gas_limit) / 1e9
        
        # Estimate USD cost (would need price oracle)
        eth_price_usd = 2000.0  # Placeholder
        cost_usd = cost_eth * eth_price_usd
        
        return {
            "gas_price_gwei": gas_price,
            "gas_limit": gas_limit,
            "cost_eth": cost_eth,
            "cost_usd": cost_usd,
            "speed": speed
        }
    
    def get_optimal_gas_price(self, 
                            chain: ChainType, 
                            max_wait_minutes: int = 5) -> Optional[float]:
        """Get optimal gas price for target confirmation time."""
        current_prices = self.get_gas_prices(chain)
        
        if not current_prices:
            return None
        
        # Simple mapping of wait time to gas price tier
        if max_wait_minutes <= 1:
            return current_prices.get("instant")
        elif max_wait_minutes <= 3:
            return current_prices.get("fast")
        elif max_wait_minutes <= 10:
            return current_prices.get("standard")
        else:
            return current_prices.get("slow")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get gas oracle statistics."""
        stats = {}
        
        for chain in self._gas_history.keys():
            history = self._gas_history[chain]
            current = self._current_prices.get(chain)
            
            if history and current:
                recent_prices = [gp.standard for gp in history[-20:]]
                
                stats[chain.value] = {
                    "current_standard": current.standard,
                    "24h_avg": statistics.mean([gp.standard for gp in history]),
                    "24h_min": min(gp.standard for gp in history),
                    "24h_max": max(gp.standard for gp in history),
                    "recent_volatility": statistics.stdev(recent_prices) if len(recent_prices) > 1 else 0,
                    "congestion_level": self._congestion_levels[chain].value,
                    "data_points": len(history)
                }
        
        return stats