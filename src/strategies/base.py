"""
Base Strategy Framework

Provides the foundation for all trading strategies with:
- Strategy lifecycle management
- Signal generation interface
- Risk management integration
- Performance tracking
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging

from src.core.base import Component as BaseComponent
from src.core.events import Event


class StrategyState(Enum):
    """Strategy operational states."""
    INITIALIZING = "INITIALIZING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class SignalType(Enum):
    """Types of trading signals."""
    BUY = "BUY"
    SELL = "SELL"
    CLOSE_LONG = "CLOSE_LONG"
    CLOSE_SHORT = "CLOSE_SHORT"
    HOLD = "HOLD"


class StrategyResult(Enum):
    """Strategy execution results."""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    NO_ACTION = "NO_ACTION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    RISK_LIMIT_EXCEEDED = "RISK_LIMIT_EXCEEDED"


@dataclass
class StrategySignal:
    """Container for strategy-generated signals."""
    signal_type: SignalType
    pair: str
    confidence: float  # 0.0 to 1.0
    size: Optional[float] = None
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Dict[str, Any] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class StrategyConfig:
    """Base strategy configuration."""
    name: str
    enabled: bool = True
    pairs: List[str] = None
    max_positions: int = 5
    max_risk_per_trade: float = 0.02  # 2%
    max_portfolio_risk: float = 0.10   # 10%
    min_confidence: float = 0.6
    position_sizing_method: str = "fixed_fractional"
    parameters: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.pairs is None:
            self.pairs = []
        if self.parameters is None:
            self.parameters = {}


@dataclass
class StrategyMetrics:
    """Strategy performance metrics."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    active_positions: int = 0
    last_updated: datetime = None
    
    def update_metrics(self, trade_pnl: float = None):
        """Update metrics after trade completion."""
        if trade_pnl is not None:
            self.total_trades += 1
            self.total_pnl += trade_pnl
            
            if trade_pnl > 0:
                self.winning_trades += 1
            else:
                self.losing_trades += 1
            
            # Recalculate derived metrics
            if self.total_trades > 0:
                self.win_rate = self.winning_trades / self.total_trades
            
            if self.winning_trades > 0:
                self.avg_win = sum([p for p in [trade_pnl] if p > 0]) / self.winning_trades
            
            if self.losing_trades > 0:
                self.avg_loss = abs(sum([p for p in [trade_pnl] if p < 0]) / self.losing_trades)
        
        self.last_updated = datetime.now()


class BaseStrategy(BaseComponent, ABC):
    """
    Abstract base class for all trading strategies.
    
    Provides common functionality:
    - Event handling
    - Signal generation
    - Risk management
    - Performance tracking
    """
    
    def __init__(self, config: StrategyConfig):
        super().__init__()
        self.config = config
        self.state = StrategyState.INITIALIZING
        self.metrics = StrategyMetrics()
        self.logger = logging.getLogger(f"{__name__}.{config.name}")
        
        # Internal tracking
        self._positions = {}  # pair -> position info
        self._orders = {}     # order_id -> order info
        self._signals = []    # Recent signals
        self._market_data = {}  # pair -> latest market data
        
        self.logger.info(f"Strategy {config.name} initialized")
    
    # Abstract methods that strategies must implement
    @abstractmethod
    async def analyze_market(self, market_data: Event) -> List[StrategySignal]:
        """
        Analyze market data and generate trading signals.
        
        Args:
            market_data: Market data event
            
        Returns:
            List of generated signals
        """
        pass
    
    @abstractmethod
    def validate_signal(self, signal: StrategySignal) -> bool:
        """
        Validate a signal before execution.
        
        Args:
            signal: Signal to validate
            
        Returns:
            True if signal is valid
        """
        pass
    
    @abstractmethod
    def calculate_position_size(self, signal: StrategySignal, account_balance: float) -> float:
        """
        Calculate position size for a signal.
        
        Args:
            signal: Trading signal
            account_balance: Current account balance
            
        Returns:
            Position size
        """
        pass
    
    # Event handlers
    async def handle_market_data(self, event: Event) -> List[Event]:
        """Handle incoming market data."""
        try:
            if self.state != StrategyState.ACTIVE:
                return []
            
            # Update internal market data cache
            self._market_data[event.pair] = event
            
            # Only analyze pairs we're interested in
            if self.config.pairs and event.pair not in self.config.pairs:
                return []
            
            # Generate signals
            signals = await self.analyze_market(event)
            
            # Process and emit valid signals
            events = []
            for signal in signals:
                if self._should_process_signal(signal):
                    signal_event = self._create_signal_event(signal)
                    events.append(signal_event)
                    self._signals.append(signal)
                    
                    self.logger.info(
                        f"Signal generated: {signal.signal_type.value} {signal.pair} "
                        f"confidence={signal.confidence:.2f}"
                    )
            
            return events
            
        except Exception as e:
            self.logger.error(f"Error handling market data: {e}")
            self.state = StrategyState.ERROR
            return []
    
    async def handle_position_event(self, event: Event) -> List[Event]:
        """Handle position updates."""
        try:
            # Update position tracking
            self._positions[event.pair] = {
                'size': event.size,
                'entry_price': event.entry_price,
                'current_price': event.current_price,
                'unrealized_pnl': event.unrealized_pnl,
                'timestamp': event.timestamp
            }
            
            # Update metrics
            self.metrics.active_positions = len([p for p in self._positions.values() if p['size'] != 0])
            self.metrics.unrealized_pnl = sum(p['unrealized_pnl'] for p in self._positions.values())
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error handling position event: {e}")
            return []
    
    async def handle_order_event(self, event: Event) -> List[Event]:
        """Handle order updates."""
        try:
            # Track order status
            self._orders[event.order_id] = {
                'status': event.status,
                'pair': event.pair,
                'side': event.side,
                'size': event.size,
                'price': event.price,
                'timestamp': event.timestamp
            }
            
            # Update metrics on trade completion
            if event.status == 'FILLED':
                self.metrics.update_metrics()
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error handling order event: {e}")
            return []
    
    # Strategy management
    def start(self):
        """Start the strategy."""
        if self.state in [StrategyState.INITIALIZING, StrategyState.PAUSED, StrategyState.STOPPED]:
            self.state = StrategyState.ACTIVE
            self.logger.info(f"Strategy {self.config.name} started")
    
    def pause(self):
        """Pause the strategy."""
        if self.state == StrategyState.ACTIVE:
            self.state = StrategyState.PAUSED
            self.logger.info(f"Strategy {self.config.name} paused")
    
    def stop(self):
        """Stop the strategy."""
        self.state = StrategyState.STOPPED
        self.logger.info(f"Strategy {self.config.name} stopped")
    
    def reset(self):
        """Reset strategy state."""
        self.metrics = StrategyMetrics()
        self._positions.clear()
        self._orders.clear()
        self._signals.clear()
        self.state = StrategyState.INITIALIZING
        self.logger.info(f"Strategy {self.config.name} reset")
    
    # Helper methods
    def _should_process_signal(self, signal: StrategySignal) -> bool:
        """Check if signal should be processed."""
        # Check basic validation
        if not self.validate_signal(signal):
            return False
        
        # Check confidence threshold
        if signal.confidence < self.config.min_confidence:
            self.logger.debug(f"Signal confidence {signal.confidence:.2f} below threshold {self.config.min_confidence}")
            return False
        
        # Check position limits
        if self.metrics.active_positions >= self.config.max_positions:
            self.logger.debug("Maximum positions reached")
            return False
        
        # Check if already have position in this pair
        current_position = self._positions.get(signal.pair, {})
        if current_position.get('size', 0) != 0:
            # Already have position, only allow closing signals
            if signal.signal_type not in [SignalType.CLOSE_LONG, SignalType.CLOSE_SHORT]:
                self.logger.debug(f"Already have position in {signal.pair}")
                return False
        
        return True
    
    def _create_signal_event(self, signal: StrategySignal) -> Event:
        """Create SignalEvent from StrategySignal."""
        # Create a basic event with signal data
        return Event(
            event_type="SIGNAL",
            data={
                'pair': signal.pair,
                'signal_type': signal.signal_type.value,
                'confidence': signal.confidence,
                'size': signal.size,
                'price': signal.price,
                'stop_loss': signal.stop_loss,
                'take_profit': signal.take_profit,
                'strategy': self.config.name,
                'metadata': signal.metadata or {}
            }
        )
    
    def get_position(self, pair: str) -> Optional[Dict[str, Any]]:
        """Get current position for pair."""
        return self._positions.get(pair)
    
    def get_latest_data(self, pair: str) -> Optional[Event]:
        """Get latest market data for pair."""
        return self._market_data.get(pair)
    
    def is_active(self) -> bool:
        """Check if strategy is active."""
        return self.state == StrategyState.ACTIVE
    
    def get_status(self) -> Dict[str, Any]:
        """Get strategy status summary."""
        return {
            'name': self.config.name,
            'state': self.state.value,
            'metrics': {
                'total_trades': self.metrics.total_trades,
                'win_rate': self.metrics.win_rate,
                'total_pnl': self.metrics.total_pnl,
                'active_positions': self.metrics.active_positions,
                'sharpe_ratio': self.metrics.sharpe_ratio
            },
            'positions': len(self._positions),
            'recent_signals': len(self._signals[-10:])  # Last 10 signals
        }