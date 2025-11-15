"""
Simple event bus and event definitions for position monitoring.

This provides a lightweight event system for the position monitoring components.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Callable, List, Optional
from collections import defaultdict
from enum import Enum
import asyncio
import logging


logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================

class OrderSide(str, Enum):
    """Order side enumeration."""
    BUY = "buy"
    SELL = "sell"
    LONG = "long"
    SHORT = "short"


# ============================================================================
# Base Event Classes
# ============================================================================

@dataclass
class Event:
    """Base class for all events."""
    timestamp: datetime
    metadata: Dict[str, Any]


# ============================================================================
# Position Events
# ============================================================================

@dataclass
class PositionOpened(Event):
    """Position opened successfully."""
    position_id: str
    symbol: str
    side: OrderSide
    entry_price: float
    quantity: float
    exchange: str
    market_type: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop_distance_pct: float = 0.5
    signal_id: Optional[str] = None
    order_id: Optional[str] = None


@dataclass
class PositionClosed(Event):
    """Position closed."""
    position_id: str
    symbol: str
    side: OrderSide
    entry_price: float
    exit_price: float
    quantity: float
    exchange: str
    realized_pnl: float
    realized_pnl_pct: float
    exit_reason: str
    hold_duration_seconds: float


@dataclass
class PositionUpdated(Event):
    """Position updated."""
    position_id: str
    symbol: str
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


# ============================================================================
# Risk Management Events
# ============================================================================

@dataclass
class DumpDetected(Event):
    """Dump detected."""
    position_id: str
    symbol: str
    signals: List[str]


@dataclass
class PortfolioHealthDegraded(Event):
    """Portfolio health degraded."""
    health_score: float
    action: str


@dataclass
class CorrelatedDumpDetected(Event):
    """Correlated dump detected."""
    leader_symbol: str
    dump_pct: float
    affected_positions: List[str]


@dataclass
class CircuitBreakerTriggered(Event):
    """Circuit breaker triggered."""
    level: int
    drawdown_pct: float
    action: str


@dataclass
class MaxHoldTimeExceeded(Event):
    """Max hold time exceeded."""
    position_id: str
    symbol: str
    hold_time_minutes: float


@dataclass
class ForceExitRequired(Event):
    """Force exit required."""
    position_id: str
    reason: str


@dataclass
class StopNewEntries(Event):
    """Stop new entries."""
    reason: str


@dataclass
class StopAllTrading(Event):
    """Stop all trading."""
    reason: str


# ============================================================================
# Event Bus
# ============================================================================

class EventBus:
    """
    Event bus for publish-subscribe pattern.

    Allows components to subscribe to events and publish events asynchronously.
    """

    def __init__(self):
        """Initialize the event bus."""
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self.logger = logging.getLogger(f"{__name__}.EventBus")

    async def subscribe(self, event_type: str, callback: Callable):
        """
        Subscribe to an event type.

        Args:
            event_type: Type of event to subscribe to
            callback: Async callback function
        """
        async with self._lock:
            self._subscribers[event_type].append(callback)
            self.logger.debug(f"Subscribed to {event_type}: {callback.__name__}")

    async def publish(self, event: Event):
        """
        Publish an event to all subscribers.

        Args:
            event: Event object to publish
        """
        # Get event type from class name
        event_type = event.__class__.__name__

        # Get subscribers
        async with self._lock:
            callbacks = self._subscribers[event_type].copy()

        # Call all subscribers
        if callbacks:
            tasks = []
            for callback in callbacks:
                try:
                    task = asyncio.create_task(callback(event))
                    tasks.append(task)
                except Exception as e:
                    self.logger.error(f"Error creating task for {callback.__name__}: {e}")

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        self.logger.error(
                            f"Error in subscriber {callbacks[i].__name__}: {result}"
                        )


# Global event bus instance
event_bus = EventBus()
