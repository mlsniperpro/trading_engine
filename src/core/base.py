"""
Base classes for all trading engine components.

Provides:
- Component: Base class for all components
- AlwaysOnComponent: For 24/7 running components (data streams, analytics, position monitor)
- ReactiveComponent: For event-triggered components (decision engine, execution engine)
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from .event_bus import EventBus

logger = logging.getLogger(__name__)


# ============================================================================
# Base Component
# ============================================================================

class Component(ABC):
    """
    Base class for all trading engine components.

    Provides:
    - Standard initialization and cleanup hooks
    - Health check support
    - Lifecycle management (started/stopped state)
    - Component name and logging

    All components should inherit from this class or one of its subclasses.
    """

    def __init__(self, name: str, event_bus: Optional[EventBus] = None):
        """
        Initialize the component.

        Args:
            name: Component name for logging and identification
            event_bus: Optional event bus for pub/sub
        """
        self.name = name
        self.event_bus = event_bus
        self._started = False
        self._started_at: Optional[datetime] = None
        self._logger = logging.getLogger(f"{self.__class__.__module__}.{name}")

    async def initialize(self) -> None:
        """
        Initialize the component (one-time setup).

        Override this method to perform initialization that requires
        async operations (e.g., connecting to databases, exchanges).

        This is called before start().
        """
        self._logger.info("Initializing %s", self.name)

    async def start(self) -> None:
        """
        Start the component.

        Override this method to start background tasks, subscriptions, etc.
        """
        if self._started:
            self._logger.warning("%s already started", self.name)
            return

        self._logger.info("Starting %s", self.name)
        self._started = True
        self._started_at = datetime.utcnow()

    async def stop(self) -> None:
        """
        Stop the component gracefully.

        Override this method to clean up resources, close connections, etc.
        """
        if not self._started:
            self._logger.warning("%s not started", self.name)
            return

        self._logger.info("Stopping %s", self.name)
        self._started = False

    async def health_check(self) -> dict:
        """
        Perform health check and return status.

        Override this method to implement component-specific health checks.

        Returns:
            Dictionary with health status:
            {
                "status": "healthy" | "degraded" | "unhealthy",
                "uptime_seconds": float,
                "details": {...}
            }
        """
        uptime = (
            (datetime.utcnow() - self._started_at).total_seconds()
            if self._started_at
            else 0
        )

        return {
            "component": self.name,
            "status": "healthy" if self._started else "stopped",
            "uptime_seconds": uptime,
            "details": {},
        }

    @property
    def is_started(self) -> bool:
        """Check if component is started."""
        return self._started

    @property
    def uptime_seconds(self) -> float:
        """Get component uptime in seconds."""
        if not self._started_at:
            return 0.0
        return (datetime.utcnow() - self._started_at).total_seconds()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, started={self._started})"


# ============================================================================
# Always-On Component
# ============================================================================

class AlwaysOnComponent(Component):
    """
    Base class for components that run 24/7.

    Examples:
    - Data streaming (WebSocket connections)
    - Analytics engine (continuous calculations)
    - Position monitor (continuous monitoring)
    - Event bus (continuous event processing)

    These components have a main loop that runs continuously.
    """

    def __init__(self, name: str, event_bus: Optional[EventBus] = None):
        """
        Initialize always-on component.

        Args:
            name: Component name
            event_bus: Event bus for pub/sub
        """
        super().__init__(name, event_bus)
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the always-on component and its main loop."""
        await super().start()

        if self._running:
            self._logger.warning("%s already running", self.name)
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name=f"{self.name}_loop")
        self._logger.info(" %s started (24/7 mode)", self.name)

    async def stop(self) -> None:
        """Stop the always-on component gracefully."""
        self._logger.info("Stopping %s...", self.name)
        self._running = False

        # Wait for main loop to finish
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
                self._logger.info(" %s stopped gracefully", self.name)
            except asyncio.TimeoutError:
                self._logger.warning("%s shutdown timeout - forcing stop", self.name)
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

        await super().stop()

    @abstractmethod
    async def _run_loop(self) -> None:
        """
        Main 24/7 loop (MUST be implemented by subclasses).

        This method should run continuously while self._running is True.

        Example:
            async def _run_loop(self):
                while self._running:
                    try:
                        await self.do_work()
                        await asyncio.sleep(0.1)
                    except Exception as e:
                        self._logger.exception("Error in loop: %s", e)
        """
        raise NotImplementedError("Subclasses must implement _run_loop()")

    @property
    def is_running(self) -> bool:
        """Check if the main loop is running."""
        return self._running


# ============================================================================
# Reactive Component
# ============================================================================

class ReactiveComponent(Component):
    """
    Base class for event-triggered components.

    Examples:
    - Decision engine (reacts to analytics events)
    - Execution engine (reacts to trading signals)
    - Notification system (reacts to important events)

    These components subscribe to events and react when events occur.
    They do not have a continuous loop.
    """

    def __init__(self, name: str, event_bus: EventBus):
        """
        Initialize reactive component.

        Args:
            name: Component name
            event_bus: Event bus for subscribing to events
        """
        super().__init__(name, event_bus)

        if not event_bus:
            raise ValueError("ReactiveComponent requires an EventBus")

    async def start(self) -> None:
        """Start the reactive component and subscribe to events."""
        await super().start()
        await self._subscribe_to_events()
        self._logger.info(" %s started (reactive mode)", self.name)

    async def stop(self) -> None:
        """Stop the reactive component and unsubscribe from events."""
        self._logger.info("Stopping %s...", self.name)
        await self._unsubscribe_from_events()
        await super().stop()
        self._logger.info(" %s stopped", self.name)

    @abstractmethod
    async def _subscribe_to_events(self) -> None:
        """
        Subscribe to events (MUST be implemented by subclasses).

        Example:
            async def _subscribe_to_events(self):
                self.event_bus.subscribe(OrderFlowImbalanceDetected, self._on_imbalance)
                self.event_bus.subscribe(MicrostructurePatternDetected, self._on_pattern)
        """
        raise NotImplementedError("Subclasses must implement _subscribe_to_events()")

    async def _unsubscribe_from_events(self) -> None:
        """
        Unsubscribe from events.

        Override this method to clean up subscriptions.
        Default implementation does nothing (EventBus handles cleanup).
        """
        self._logger.debug("Unsubscribing from events")
        # EventBus will handle cleanup if component holds no references


# ============================================================================
# Example Usage (for documentation)
# ============================================================================

# Example Always-On Component:
class ExampleDataStream(AlwaysOnComponent):
    """Example 24/7 data streaming component."""

    async def _run_loop(self) -> None:
        """Main loop that streams data continuously."""
        self._logger.info("Data stream started")

        while self._running:
            try:
                # Simulate data streaming
                await asyncio.sleep(1.0)
                # In real implementation: receive WebSocket data, publish events

            except Exception as e:
                self._logger.exception("Error in data stream: %s", e)


# Example Reactive Component:
class ExampleDecisionEngine(ReactiveComponent):
    """Example reactive decision engine."""

    async def _subscribe_to_events(self) -> None:
        """Subscribe to analytics events."""
        # In real implementation:
        # self.event_bus.subscribe(OrderFlowImbalanceDetected, self._on_imbalance)
        self._logger.info("Subscribed to analytics events")

    async def _on_imbalance(self, event):
        """React to order flow imbalance event."""
        self._logger.info("Processing imbalance event: %s", event)
        # In real implementation: evaluate signal, publish TradingSignalGenerated
