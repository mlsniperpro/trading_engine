"""
Bid-Ask Bounce Strategy

Primary market-making strategy that captures spread by:
- Placing orders at bid/ask levels
- Scalping small price movements
- Managing inventory risk
- Adapting to market conditions

This is the core profit-generation strategy from the design spec.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
from datetime import datetime, timedelta

from src.strategies.base import (
    BaseStrategy, StrategySignal, StrategyConfig, SignalType
)
from src.core.events import Event
from src.utils.math_utils import StatisticalUtils, RiskMetrics
from src.utils.formatters import PriceFormatter


@dataclass
class BidAskBounceConfig(StrategyConfig):
    """Configuration for bid-ask bounce strategy."""
    # Spread parameters
    min_spread_bps: float = 5.0      # Minimum spread in basis points
    max_spread_bps: float = 50.0     # Maximum spread to trade
    target_spread_bps: float = 15.0   # Target spread for entries
    
    # Position management
    max_inventory_ratio: float = 0.5  # Max inventory as % of daily volume
    inventory_decay_minutes: int = 30 # Max time to hold inventory
    
    # Market making parameters
    order_size_ratio: float = 0.01   # Order size as % of recent volume
    min_order_size: float = 10.0     # Minimum order size
    max_order_size: float = 1000.0   # Maximum order size
    
    # Risk management
    max_adverse_move_bps: float = 25.0  # Stop loss threshold
    profit_target_ratio: float = 2.0    # Profit target as ratio of risk
    
    # Market conditions
    min_volume_ratio: float = 0.1    # Min volume vs avg to trade
    max_volatility_ratio: float = 2.0  # Max volatility vs avg to trade
    trend_threshold: float = 0.3     # Trend strength threshold
    
    # Timing
    entry_timeout_seconds: int = 10   # Order timeout
    rebalance_interval_seconds: int = 5  # Position rebalancing


class BidAskBounceStrategy(BaseStrategy):
    """
    Market-making strategy that profits from bid-ask spread capture.
    
    Core Logic:
    1. Monitor order book for spread opportunities
    2. Place orders at favorable bid/ask levels
    3. Manage inventory to stay market neutral
    4. Scale out of positions quickly on adverse moves
    
    Risk Management:
    - Position sizing based on volatility
    - Inventory limits prevent large directional exposure
    - Time-based exits prevent stale positions
    """
    
    def __init__(self, config: BidAskBounceConfig):
        super().__init__(config)
        self.config: BidAskBounceConfig = config
        self.logger = logging.getLogger(f"{__name__}.BidAskBounce")
        
        # Strategy state
        self._inventory = {}  # pair -> current inventory
        self._order_history = []  # Recent order history
        self._market_stats = {}   # pair -> market statistics
        self._last_rebalance = {}  # pair -> last rebalance time
        
        # Performance tracking
        self._spread_captures = 0
        self._inventory_turns = 0
        self._adverse_exits = 0
        
        self.logger.info("Bid-Ask Bounce strategy initialized")
    
    async def analyze_market(self, market_data: Event) -> List[StrategySignal]:
        """
        Analyze market for bid-ask bounce opportunities.
        
        Strategy Flow:
        1. Check market conditions (spread, volume, volatility)
        2. Calculate optimal order sizes and levels
        3. Generate signals for market making orders
        4. Include inventory management signals
        """
        try:
            signals = []
            pair = market_data.pair
            
            # Update market statistics
            self._update_market_stats(market_data)
            
            # Check if market is suitable for market making
            if not self._is_suitable_market(market_data):
                return signals
            
            # Get current inventory
            current_inventory = self._inventory.get(pair, 0.0)
            
            # Check if need to rebalance inventory
            if self._should_rebalance(pair):
                rebalance_signal = self._generate_rebalance_signal(market_data, current_inventory)
                if rebalance_signal:
                    signals.append(rebalance_signal)
                return signals
            
            # Generate market making signals
            mm_signals = self._generate_market_making_signals(market_data, current_inventory)
            signals.extend(mm_signals)
            
            # Update last analysis time
            self._last_rebalance[pair] = datetime.now()
            
            return signals
            
        except Exception as e:
            self.logger.error(f"Error in market analysis: {e}")
            return []
    
    def _update_market_stats(self, market_data: Event):
        """Update rolling market statistics."""
        pair = market_data.pair
        
        if pair not in self._market_stats:
            self._market_stats[pair] = {
                'spreads': [],
                'volumes': [],
                'prices': [],
                'volatility': 0.0,
                'avg_spread': 0.0,
                'avg_volume': 0.0,
                'last_update': datetime.now()
            }
        
        stats = self._market_stats[pair]
        
        # Calculate current spread
        if market_data.bid and market_data.ask:
            spread_bps = ((market_data.ask - market_data.bid) / market_data.bid) * 10000
            stats['spreads'].append(spread_bps)
            stats['spreads'] = stats['spreads'][-100:]  # Keep last 100
            stats['avg_spread'] = sum(stats['spreads']) / len(stats['spreads'])
        
        # Track volume
        if market_data.volume_24h:
            hourly_volume = market_data.volume_24h / 24
            stats['volumes'].append(hourly_volume)
            stats['volumes'] = stats['volumes'][-100:]
            stats['avg_volume'] = sum(stats['volumes']) / len(stats['volumes'])
        
        # Track prices for volatility
        if market_data.price:
            stats['prices'].append(market_data.price)
            stats['prices'] = stats['prices'][-100:]
            
            if len(stats['prices']) > 10:
                returns = StatisticalUtils.simple_returns(stats['prices'])
                stats['volatility'] = StatisticalUtils.rolling_std(returns, min(20, len(returns)))[-1] if returns else 0.0
        
        stats['last_update'] = datetime.now()
    
    def _is_suitable_market(self, market_data: Event) -> bool:
        """Check if market conditions are suitable for market making."""
        pair = market_data.pair
        stats = self._market_stats.get(pair, {})
        
        # Need basic market data
        if not (market_data.bid and market_data.ask and market_data.price):
            return False
        
        # Calculate current spread
        spread_bps = ((market_data.ask - market_data.bid) / market_data.bid) * 10000
        
        # Check spread bounds
        if spread_bps < self.config.min_spread_bps or spread_bps > self.config.max_spread_bps:
            self.logger.debug(f"Spread {spread_bps:.1f}bp outside bounds [{self.config.min_spread_bps}-{self.config.max_spread_bps}]")
            return False
        
        # Check volume (if available)
        if stats.get('avg_volume', 0) > 0:
            current_volume = market_data.volume_24h / 24 if market_data.volume_24h else 0
            volume_ratio = current_volume / stats['avg_volume']
            
            if volume_ratio < self.config.min_volume_ratio:
                self.logger.debug(f"Volume ratio {volume_ratio:.2f} below minimum {self.config.min_volume_ratio}")
                return False
        
        # Check volatility (if available)
        if stats.get('volatility', 0) > 0:
            current_vol = stats['volatility']
            avg_vol = sum([s.get('volatility', 0) for s in self._market_stats.values()]) / len(self._market_stats)
            
            if avg_vol > 0 and current_vol / avg_vol > self.config.max_volatility_ratio:
                self.logger.debug(f"Volatility ratio {current_vol/avg_vol:.2f} above maximum {self.config.max_volatility_ratio}")
                return False
        
        return True
    
    def _generate_market_making_signals(self, market_data: Event, current_inventory: float) -> List[StrategySignal]:
        """Generate market making buy/sell signals."""
        signals = []
        pair = market_data.pair
        
        # Calculate order size
        order_size = self._calculate_order_size(market_data)
        
        if order_size == 0:
            return signals
        
        # Adjust for inventory bias
        inventory_bias = self._calculate_inventory_bias(current_inventory, order_size)
        
        # Generate buy signal (bid side)
        if inventory_bias >= 0:  # Neutral or short inventory - can buy
            buy_price = market_data.bid
            buy_size = order_size * (1 + inventory_bias)
            
            # Calculate stop loss and take profit
            stop_loss = buy_price * (1 - self.config.max_adverse_move_bps / 10000)
            take_profit = buy_price * (1 + (self.config.max_adverse_move_bps * self.config.profit_target_ratio) / 10000)
            
            buy_signal = StrategySignal(
                signal_type=SignalType.BUY,
                pair=pair,
                confidence=0.8,  # High confidence for market making
                size=buy_size,
                price=buy_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                metadata={
                    'strategy_type': 'market_making',
                    'side': 'bid',
                    'spread_bps': ((market_data.ask - market_data.bid) / market_data.bid) * 10000,
                    'inventory_bias': inventory_bias
                }
            )
            signals.append(buy_signal)
        
        # Generate sell signal (ask side)
        if inventory_bias <= 0:  # Neutral or long inventory - can sell
            sell_price = market_data.ask
            sell_size = order_size * (1 - inventory_bias)
            
            # Calculate stop loss and take profit
            stop_loss = sell_price * (1 + self.config.max_adverse_move_bps / 10000)
            take_profit = sell_price * (1 - (self.config.max_adverse_move_bps * self.config.profit_target_ratio) / 10000)
            
            sell_signal = StrategySignal(
                signal_type=SignalType.SELL,
                pair=pair,
                confidence=0.8,
                size=sell_size,
                price=sell_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                metadata={
                    'strategy_type': 'market_making',
                    'side': 'ask',
                    'spread_bps': ((market_data.ask - market_data.bid) / market_data.bid) * 10000,
                    'inventory_bias': inventory_bias
                }
            )
            signals.append(sell_signal)
        
        return signals
    
    def _calculate_order_size(self, market_data: Event) -> float:
        """Calculate optimal order size based on market conditions."""
        pair = market_data.pair
        stats = self._market_stats.get(pair, {})
        
        # Base size from volume ratio
        base_size = self.config.min_order_size
        
        if stats.get('avg_volume', 0) > 0:
            volume_based_size = stats['avg_volume'] * self.config.order_size_ratio
            base_size = max(base_size, volume_based_size)
        
        # Adjust for volatility (smaller size in high volatility)
        if stats.get('volatility', 0) > 0:
            vol_adjustment = min(1.0, 1.0 / (1.0 + stats['volatility'] * 10))
            base_size *= vol_adjustment
        
        # Apply limits
        order_size = max(self.config.min_order_size, min(self.config.max_order_size, base_size))
        
        return order_size
    
    def _calculate_inventory_bias(self, current_inventory: float, order_size: float) -> float:
        """
        Calculate inventory bias to manage position risk.
        
        Returns:
            Bias between -1 and 1:
            - Positive: Bias toward buying (inventory short)
            - Negative: Bias toward selling (inventory long)
            - Zero: Neutral
        """
        if order_size == 0:
            return 0.0
        
        # Normalize inventory relative to typical order size
        max_inventory = self.config.max_inventory_ratio * order_size * 10  # 10x order size as max
        
        if max_inventory == 0:
            return 0.0
        
        # Calculate bias
        inventory_ratio = current_inventory / max_inventory
        bias = -inventory_ratio  # Negative inventory (short) = positive bias (buy more)
        
        # Clamp between -1 and 1
        return max(-1.0, min(1.0, bias))
    
    def _should_rebalance(self, pair: str) -> bool:
        """Check if inventory needs rebalancing."""
        current_inventory = abs(self._inventory.get(pair, 0.0))
        
        # Check inventory limits
        stats = self._market_stats.get(pair, {})
        max_inventory = self.config.max_inventory_ratio * stats.get('avg_volume', 1000.0)
        
        if current_inventory > max_inventory:
            return True
        
        # Check time-based rebalancing
        last_rebalance = self._last_rebalance.get(pair)
        if last_rebalance:
            time_since = datetime.now() - last_rebalance
            if time_since.total_seconds() > self.config.inventory_decay_minutes * 60:
                return True
        
        return False
    
    def _generate_rebalance_signal(self, market_data: Event, current_inventory: float) -> Optional[StrategySignal]:
        """Generate signal to rebalance inventory."""
        if abs(current_inventory) < self.config.min_order_size:
            return None
        
        pair = market_data.pair
        
        # Determine rebalance direction
        if current_inventory > 0:  # Long inventory - sell to reduce
            signal_type = SignalType.SELL
            size = min(abs(current_inventory), self.config.max_order_size)
            price = market_data.bid  # Sell at bid for quick execution
        else:  # Short inventory - buy to reduce
            signal_type = SignalType.BUY
            size = min(abs(current_inventory), self.config.max_order_size)
            price = market_data.ask  # Buy at ask for quick execution
        
        return StrategySignal(
            signal_type=signal_type,
            pair=pair,
            confidence=0.9,  # High confidence for risk management
            size=size,
            price=price,
            metadata={
                'strategy_type': 'inventory_rebalance',
                'current_inventory': current_inventory,
                'rebalance_reason': 'inventory_limit' if abs(current_inventory) > self.config.max_inventory_ratio else 'time_decay'
            }
        )
    
    def validate_signal(self, signal: StrategySignal) -> bool:
        """Validate signal before execution."""
        try:
            # Basic validation
            if signal.size <= 0 or signal.confidence <= 0:
                return False
            
            # Check price bounds
            if signal.price and signal.price <= 0:
                return False
            
            # Check size bounds
            if signal.size < self.config.min_order_size or signal.size > self.config.max_order_size:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating signal: {e}")
            return False
    
    def calculate_position_size(self, signal: StrategySignal, account_balance: float) -> float:
        """Calculate position size based on risk management."""
        # Use fixed fractional sizing
        risk_amount = account_balance * self.config.max_risk_per_trade
        
        if signal.stop_loss and signal.price:
            stop_distance = abs(signal.price - signal.stop_loss)
            max_size = risk_amount / stop_distance if stop_distance > 0 else signal.size
            return min(signal.size, max_size)
        
        return signal.size
    
    def update_inventory(self, pair: str, size_change: float):
        """Update inventory tracking after trade execution."""
        if pair not in self._inventory:
            self._inventory[pair] = 0.0
        
        self._inventory[pair] += size_change
        self._inventory_turns += 1
        
        self.logger.debug(f"Inventory updated: {pair} = {self._inventory[pair]:.2f}")
    
    def get_strategy_metrics(self) -> Dict[str, Any]:
        """Get strategy-specific metrics."""
        total_inventory = sum(abs(inv) for inv in self._inventory.values())
        
        return {
            'spread_captures': self._spread_captures,
            'inventory_turns': self._inventory_turns,
            'adverse_exits': self._adverse_exits,
            'total_inventory': total_inventory,
            'active_pairs': len([p for p, inv in self._inventory.items() if abs(inv) > 0]),
            'avg_spread': sum(stats.get('avg_spread', 0) for stats in self._market_stats.values()) / max(1, len(self._market_stats))
        }