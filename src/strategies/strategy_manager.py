"""
Strategy Manager

Coordinates multiple trading strategies:
- Strategy lifecycle management
- Signal aggregation and conflict resolution
- Performance monitoring
- Risk allocation across strategies
"""

from typing import Dict, List, Any, Optional, Type
from datetime import datetime, timedelta
import asyncio
import logging
from dataclasses import dataclass

from src.core.base import Component as BaseComponent
from src.core.events import Event
from src.strategies.base import BaseStrategy, StrategyConfig, StrategyState, StrategySignal, SignalType
from src.strategies.bid_ask_bounce import BidAskBounceStrategy, BidAskBounceConfig
from src.utils.metrics import get_trading_metrics


@dataclass
class StrategyAllocation:
    """Strategy resource allocation."""
    strategy_name: str
    max_capital_pct: float = 0.2  # Max 20% of capital per strategy
    max_positions: int = 5
    priority: int = 1  # Higher number = higher priority
    enabled: bool = True


class StrategyManager(BaseComponent):
    """
    Manages multiple trading strategies with:
    - Dynamic strategy loading/unloading
    - Signal conflict resolution
    - Performance monitoring
    - Risk allocation
    """
    
    # Registry of available strategy classes
    STRATEGY_REGISTRY = {
        'bid_ask_bounce': BidAskBounceStrategy,
        # Add more strategies here as implemented
    }
    
    def __init__(self, allocations: List[StrategyAllocation] = None):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # Strategy management
        self._strategies: Dict[str, BaseStrategy] = {}
        self._allocations: Dict[str, StrategyAllocation] = {}
        self._performance_history = {}
        
        # Signal management
        self._signal_queue = asyncio.Queue()
        self._signal_conflicts = []
        
        # Risk tracking
        self._total_capital = 100000.0  # Default capital
        self._allocated_capital = {}
        self._position_tracker = {}
        
        # Setup allocations
        if allocations:
            for allocation in allocations:
                self._allocations[allocation.strategy_name] = allocation
        
        self.logger.info("Strategy Manager initialized")
    
    async def initialize_strategies(self, strategy_configs: Dict[str, StrategyConfig]):
        """Initialize strategies from configurations."""
        for strategy_name, config in strategy_configs.items():
            try:
                await self.add_strategy(strategy_name, config)
            except Exception as e:
                self.logger.error(f"Failed to initialize strategy {strategy_name}: {e}")
    
    async def add_strategy(self, strategy_name: str, config: StrategyConfig):
        """Add a new strategy instance."""
        try:
            # Get strategy class
            strategy_class = self._get_strategy_class(config)
            if not strategy_class:
                raise ValueError(f"Unknown strategy type for {strategy_name}")
            
            # Create strategy instance
            strategy = strategy_class(config)
            
            # Setup allocation if not exists
            if strategy_name not in self._allocations:
                self._allocations[strategy_name] = StrategyAllocation(strategy_name=strategy_name)
            
            # Calculate capital allocation
            allocation = self._allocations[strategy_name]
            allocated_capital = self._total_capital * allocation.max_capital_pct
            self._allocated_capital[strategy_name] = allocated_capital
            
            # Add to managed strategies
            self._strategies[strategy_name] = strategy
            self._performance_history[strategy_name] = []
            
            self.logger.info(f"Added strategy {strategy_name} with {allocated_capital:.2f} capital allocation")
            
        except Exception as e:
            self.logger.error(f"Error adding strategy {strategy_name}: {e}")
            raise
    
    def _get_strategy_class(self, config: StrategyConfig) -> Optional[Type[BaseStrategy]]:
        """Get strategy class based on config."""
        if isinstance(config, BidAskBounceConfig):
            return BidAskBounceStrategy
        
        # Try to infer from strategy name
        strategy_type = getattr(config, 'strategy_type', config.name.lower())
        return self.STRATEGY_REGISTRY.get(strategy_type)
    
    async def remove_strategy(self, strategy_name: str):
        """Remove a strategy instance."""
        if strategy_name in self._strategies:
            strategy = self._strategies[strategy_name]
            strategy.stop()
            
            del self._strategies[strategy_name]
            del self._allocated_capital[strategy_name]
            
            self.logger.info(f"Removed strategy {strategy_name}")
    
    async def start_all_strategies(self):
        """Start all enabled strategies."""
        for strategy_name, strategy in self._strategies.items():
            allocation = self._allocations.get(strategy_name)
            if allocation and allocation.enabled:
                strategy.start()
                self.logger.info(f"Started strategy {strategy_name}")
    
    async def stop_all_strategies(self):
        """Stop all strategies."""
        for strategy_name, strategy in self._strategies.items():
            strategy.stop()
            self.logger.info(f"Stopped strategy {strategy_name}")
    
    async def handle_market_data(self, event: Event) -> List[Event]:
        """Route market data to all active strategies."""
        events = []
        
        for strategy_name, strategy in self._strategies.items():
            if strategy.is_active():
                try:
                    strategy_events = await strategy.handle_market_data(event)
                    
                    # Add strategy metadata to signals
                    for strategy_event in strategy_events:
                        if hasattr(strategy_event, 'event_type') and strategy_event.event_type == "SIGNAL":
                            strategy_event.strategy = strategy_name
                    
                    events.extend(strategy_events)
                    
                except Exception as e:
                    self.logger.error(f"Error in strategy {strategy_name} market data handling: {e}")
        
        # Process signal conflicts
        if events:
            events = await self._resolve_signal_conflicts(events)
        
        return events
    
    async def handle_order_event(self, event: Event) -> List[Event]:
        """Route order events to relevant strategies."""
        events = []
        
        strategy_name = getattr(event, 'strategy', None)
        if strategy_name and strategy_name in self._strategies:
            strategy = self._strategies[strategy_name]
            try:
                strategy_events = await strategy.handle_order_event(event)
                events.extend(strategy_events)
                
                # Update performance tracking
                if event.status == 'FILLED':
                    self._update_strategy_performance(strategy_name, event)
                    
            except Exception as e:
                self.logger.error(f"Error in strategy {strategy_name} order event handling: {e}")
        
        return events
    
    async def handle_position_event(self, event: Event) -> List[Event]:
        """Route position events to relevant strategies."""
        events = []
        
        # Update position tracking
        self._position_tracker[event.pair] = {
            'size': event.size,
            'entry_price': event.entry_price,
            'current_price': event.current_price,
            'unrealized_pnl': event.unrealized_pnl,
            'timestamp': event.timestamp
        }
        
        # Route to strategies
        for strategy_name, strategy in self._strategies.items():
            if strategy.is_active():
                try:
                    strategy_events = await strategy.handle_position_event(event)
                    events.extend(strategy_events)
                except Exception as e:
                    self.logger.error(f"Error in strategy {strategy_name} position event handling: {e}")
        
        return events
    
    async def _resolve_signal_conflicts(self, events: List[Event]) -> List[Event]:
        """Resolve conflicts between strategy signals."""
        signal_events = [e for e in events if hasattr(e, 'event_type') and e.event_type == "SIGNAL"]
        other_events = [e for e in events if not (hasattr(e, 'event_type') and e.event_type == "SIGNAL")]
        
        if len(signal_events) <= 1:
            return events
        
        # Group signals by pair
        signals_by_pair = {}
        for signal in signal_events:
            pair = signal.pair
            if pair not in signals_by_pair:
                signals_by_pair[pair] = []
            signals_by_pair[pair].append(signal)
        
        resolved_signals = []
        
        for pair, pair_signals in signals_by_pair.items():
            if len(pair_signals) == 1:
                resolved_signals.extend(pair_signals)
            else:
                # Resolve conflicts
                resolved = await self._resolve_pair_conflicts(pair, pair_signals)
                if resolved:
                    resolved_signals.extend(resolved)
        
        return other_events + resolved_signals
    
    async def _resolve_pair_conflicts(self, pair: str, signals: List[Event]) -> List[Event]:
        """Resolve conflicts for signals on the same pair."""
        if not signals:
            return []
        
        # Categorize signals
        buy_signals = [s for s in signals if s.signal_type in ['BUY']]
        sell_signals = [s for s in signals if s.signal_type in ['SELL']]
        close_signals = [s for s in signals if s.signal_type in ['CLOSE_LONG', 'CLOSE_SHORT']]
        
        resolved = []
        
        # Close signals take priority
        if close_signals:
            # Take highest confidence close signal
            best_close = max(close_signals, key=lambda s: s.confidence)
            resolved.append(best_close)
            self.logger.info(f"Resolved {pair}: Close signal priority")
            return resolved
        
        # Check for opposing signals
        if buy_signals and sell_signals:
            # Calculate net direction based on confidence and strategy priority
            buy_strength = sum(s.confidence * self._get_strategy_priority(s.strategy) for s in buy_signals)
            sell_strength = sum(s.confidence * self._get_strategy_priority(s.strategy) for s in sell_signals)
            
            if buy_strength > sell_strength * 1.1:  # 10% threshold
                # Take best buy signal
                best_buy = max(buy_signals, key=lambda s: s.confidence * self._get_strategy_priority(s.strategy))
                resolved.append(best_buy)
                self.logger.info(f"Resolved {pair}: Buy direction (strength {buy_strength:.2f} vs {sell_strength:.2f})")
            elif sell_strength > buy_strength * 1.1:
                # Take best sell signal
                best_sell = max(sell_signals, key=lambda s: s.confidence * self._get_strategy_priority(s.strategy))
                resolved.append(best_sell)
                self.logger.info(f"Resolved {pair}: Sell direction (strength {sell_strength:.2f} vs {buy_strength:.2f})")
            else:
                # Too close - skip to avoid conflicting trades
                self.logger.info(f"Resolved {pair}: Conflict too close - skipping")
                
        elif buy_signals:
            # Only buy signals - take best one
            best_buy = max(buy_signals, key=lambda s: s.confidence * self._get_strategy_priority(s.strategy))
            resolved.append(best_buy)
            
        elif sell_signals:
            # Only sell signals - take best one
            best_sell = max(sell_signals, key=lambda s: s.confidence * self._get_strategy_priority(s.strategy))
            resolved.append(best_sell)
        
        return resolved
    
    def _get_strategy_priority(self, strategy_name: str) -> float:
        """Get strategy priority for conflict resolution."""
        allocation = self._allocations.get(strategy_name)
        return allocation.priority if allocation else 1.0
    
    def _update_strategy_performance(self, strategy_name: str, order_event: OrderEvent):
        """Update strategy performance tracking."""
        if strategy_name not in self._performance_history:
            self._performance_history[strategy_name] = []
        
        performance_record = {
            'timestamp': order_event.timestamp,
            'pair': order_event.pair,
            'side': order_event.side,
            'size': order_event.size,
            'price': order_event.price,
            'order_id': order_event.order_id
        }
        
        self._performance_history[strategy_name].append(performance_record)
        
        # Keep only recent history
        cutoff = datetime.now() - timedelta(days=30)
        self._performance_history[strategy_name] = [
            record for record in self._performance_history[strategy_name]
            if record['timestamp'] > cutoff
        ]
    
    def get_strategy_status(self, strategy_name: str = None) -> Dict[str, Any]:
        """Get status of specific strategy or all strategies."""
        if strategy_name:
            if strategy_name not in self._strategies:
                return {}
            
            strategy = self._strategies[strategy_name]
            allocation = self._allocations.get(strategy_name, StrategyAllocation(strategy_name))
            
            return {
                'name': strategy_name,
                'status': strategy.get_status(),
                'allocation': {
                    'capital_pct': allocation.max_capital_pct,
                    'capital_amount': self._allocated_capital.get(strategy_name, 0),
                    'max_positions': allocation.max_positions,
                    'priority': allocation.priority,
                    'enabled': allocation.enabled
                },
                'performance': self._get_strategy_performance_summary(strategy_name)
            }
        else:
            # All strategies
            return {
                strategy_name: self.get_strategy_status(strategy_name)
                for strategy_name in self._strategies.keys()
            }
    
    def _get_strategy_performance_summary(self, strategy_name: str) -> Dict[str, Any]:
        """Get performance summary for strategy."""
        history = self._performance_history.get(strategy_name, [])
        
        if not history:
            return {'trades': 0, 'performance': 'No trades yet'}
        
        return {
            'total_trades': len(history),
            'recent_trades_24h': len([h for h in history if h['timestamp'] > datetime.now() - timedelta(hours=24)]),
            'pairs_traded': len(set(h['pair'] for h in history)),
            'last_trade': max(h['timestamp'] for h in history).isoformat()
        }
    
    def update_capital_allocation(self, total_capital: float):
        """Update total capital and recalculate allocations."""
        self._total_capital = total_capital
        
        for strategy_name, allocation in self._allocations.items():
            allocated_capital = total_capital * allocation.max_capital_pct
            self._allocated_capital[strategy_name] = allocated_capital
        
        self.logger.info(f"Updated capital allocation: Total={total_capital:.2f}")
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get overall portfolio summary."""
        total_positions = len(self._position_tracker)
        total_unrealized_pnl = sum(pos.get('unrealized_pnl', 0) for pos in self._position_tracker.values())
        active_strategies = len([s for s in self._strategies.values() if s.is_active()])
        
        return {
            'total_capital': self._total_capital,
            'active_strategies': active_strategies,
            'total_strategies': len(self._strategies),
            'total_positions': total_positions,
            'total_unrealized_pnl': total_unrealized_pnl,
            'capital_utilization': sum(self._allocated_capital.values()) / self._total_capital,
            'strategy_breakdown': {
                name: {
                    'allocation': allocation.max_capital_pct,
                    'capital': self._allocated_capital.get(name, 0),
                    'active': self._strategies[name].is_active() if name in self._strategies else False
                }
                for name, allocation in self._allocations.items()
            }
        }


# Factory functions
def create_bid_ask_bounce_manager(pairs: List[str], capital_per_strategy: float = 0.2) -> StrategyManager:
    """Create strategy manager with bid-ask bounce strategy."""
    
    # Create allocation
    allocation = StrategyAllocation(
        strategy_name='bid_ask_bounce',
        max_capital_pct=capital_per_strategy,
        max_positions=len(pairs),
        priority=1,
        enabled=True
    )
    
    # Create manager
    manager = StrategyManager([allocation])
    
    # Create strategy config
    config = BidAskBounceConfig(
        name='bid_ask_bounce',
        enabled=True,
        pairs=pairs,
        max_positions=len(pairs),
        max_risk_per_trade=0.01,  # 1% risk per trade
        min_confidence=0.7
    )
    
    # Add strategy
    asyncio.create_task(manager.add_strategy('bid_ask_bounce', config))
    
    return manager


def create_multi_strategy_manager(strategies_config: Dict[str, Any]) -> StrategyManager:
    """Create strategy manager with multiple strategies."""
    allocations = []
    
    for strategy_name, strategy_config in strategies_config.items():
        allocation = StrategyAllocation(
            strategy_name=strategy_name,
            max_capital_pct=strategy_config.get('capital_pct', 0.2),
            max_positions=strategy_config.get('max_positions', 5),
            priority=strategy_config.get('priority', 1),
            enabled=strategy_config.get('enabled', True)
        )
        allocations.append(allocation)
    
    return StrategyManager(allocations)