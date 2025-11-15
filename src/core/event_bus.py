"""
Event Bus - THE HEART of the trading engine.

The EventBus is a central message broker that runs 24/7, coordinating
all communication between components via asynchronous event publishing
and subscription.

Key Features:
- Async event queue using asyncio.Queue
- Type-safe event subscription
- Parallel handler execution with error isolation
- Statistics tracking (events/sec, handler latency, errors)
- Graceful shutdown support
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type
from weakref import WeakMethod, ref

from .events import Event, EventType

logger = logging.getLogger(__name__)


# ============================================================================
# Event Bus Statistics
# ============================================================================

@dataclass
class EventBusStats:
    """Statistics for event bus monitoring."""
    events_published: int = 0
    events_processed: int = 0
    handlers_executed: int = 0
    handler_errors: int = 0
    avg_processing_time_ms: float = 0.0
    events_per_second: float = 0.0
    queue_size: int = 0
    total_processing_time_ms: float = 0.0
    started_at: Optional[datetime] = None
    last_event_at: Optional[datetime] = None

    def get_stats_dict(self) -> Dict[str, Any]:
        """Return stats as dictionary."""
        return {
            "events_published": self.events_published,
            "events_processed": self.events_processed,
            "handlers_executed": self.handlers_executed,
            "handler_errors": self.handler_errors,
            "avg_processing_time_ms": round(self.avg_processing_time_ms, 2),
            "events_per_second": round(self.events_per_second, 2),
            "queue_size": self.queue_size,
            "uptime_seconds": (
                (datetime.utcnow() - self.started_at).total_seconds()
                if self.started_at
                else 0
            ),
        }


# ============================================================================
# Event Bus
# ============================================================================

class EventBus:
    """
    Central event distribution system.

    The EventBus runs a 24/7 event loop that:
    1. Accepts events from publishers via publish()
    2. Queues events in an async queue
    3. Dispatches events to registered handlers
    4. Isolates handler errors (one failure doesn't crash others)
    5. Tracks statistics for monitoring

    Usage:
        bus = EventBus()

        # Subscribe to events
        async def on_trade(event: TradeTickReceived):
            print(f"Trade: {event.symbol} @ {event.price}")

        bus.subscribe(TradeTickReceived, on_trade)

        # Start event loop
        await bus.start()

        # Publish events
        await bus.publish(TradeTickReceived(...))

        # Stop gracefully
        await bus.stop()
    """

    def __init__(self, max_queue_size: int = 10000):
        """
        Initialize EventBus.

        Args:
            max_queue_size: Maximum events in queue before blocking publishers
        """
        # Event queue
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=max_queue_size)

        # Subscribers: {EventType: [handler1, handler2, ...]}
        self._subscribers: Dict[Type[Event], List[Callable]] = defaultdict(list)

        # Wildcard subscribers (receive ALL events)
        self._wildcard_subscribers: List[Callable] = []

        # Event loop task
        self._running = False
        self._event_loop_task: Optional[asyncio.Task] = None

        # Statistics
        self._stats = EventBusStats()

        logger.info("EventBus initialized (max queue size: %d)", max_queue_size)

    # ========================================================================
    # Subscription Management
    # ========================================================================

    def subscribe(
        self,
        event_type: Type[Event],
        handler: Callable[[Event], Any],
        priority: int = 0,
    ) -> None:
        """
        Subscribe a handler to a specific event type.

        Args:
            event_type: Event class to subscribe to (e.g., TradeTickReceived)
            handler: Async or sync callable that accepts the event
            priority: Higher priority handlers execute first (not implemented yet)

        Note:
            Handlers can be async or sync. Async handlers are awaited,
            sync handlers are run in executor.
        """
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)
            logger.info(
                "Subscribed %s to %s (total: %d handlers)",
                handler.__name__,
                event_type.__name__,
                len(self._subscribers[event_type]),
            )
        else:
            logger.warning(
                "Handler %s already subscribed to %s",
                handler.__name__,
                event_type.__name__,
            )

    def subscribe_to_all(self, handler: Callable[[Event], Any]) -> None:
        """
        Subscribe a handler to ALL events (wildcard subscription).

        Useful for logging, monitoring, or debugging.

        Args:
            handler: Async or sync callable that accepts any event
        """
        if handler not in self._wildcard_subscribers:
            self._wildcard_subscribers.append(handler)
            logger.info("Subscribed %s to ALL events", handler.__name__)

    def unsubscribe(
        self, event_type: Type[Event], handler: Callable[[Event], Any]
    ) -> None:
        """
        Unsubscribe a handler from an event type.

        Args:
            event_type: Event class to unsubscribe from
            handler: Handler to remove
        """
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
            logger.info(
                "Unsubscribed %s from %s", handler.__name__, event_type.__name__
            )

    def unsubscribe_all(self, handler: Callable[[Event], Any]) -> None:
        """
        Unsubscribe a handler from all event types.

        Args:
            handler: Handler to remove from all subscriptions
        """
        for event_type, handlers in self._subscribers.items():
            if handler in handlers:
                handlers.remove(handler)
                logger.info(
                    "Unsubscribed %s from %s", handler.__name__, event_type.__name__
                )

        if handler in self._wildcard_subscribers:
            self._wildcard_subscribers.remove(handler)
            logger.info("Unsubscribed %s from wildcard", handler.__name__)

    def get_subscriber_count(self, event_type: Optional[Type[Event]] = None) -> int:
        """
        Get number of subscribers for an event type.

        Args:
            event_type: Specific event type, or None for total subscribers

        Returns:
            Number of subscribers
        """
        if event_type:
            return len(self._subscribers[event_type])
        else:
            return sum(len(handlers) for handlers in self._subscribers.values())

    # ========================================================================
    # Event Publishing
    # ========================================================================

    async def publish(self, event: Event) -> None:
        """
        Publish an event to the event bus.

        The event is added to the queue and will be dispatched to
        subscribers asynchronously.

        Args:
            event: Event instance to publish

        Raises:
            asyncio.QueueFull: If queue is full and timeout expires
        """
        try:
            # Non-blocking put with timeout
            await asyncio.wait_for(self._queue.put(event), timeout=1.0)
            self._stats.events_published += 1
            self._stats.last_event_at = datetime.utcnow()

            logger.debug(
                "Published event: %s (queue size: %d)",
                event.__class__.__name__,
                self._queue.qsize(),
            )

        except asyncio.TimeoutError:
            logger.error(
                "Event queue full! Dropping event: %s", event.__class__.__name__
            )
            raise asyncio.QueueFull(
                f"Event queue full (max: {self._queue.maxsize}), cannot publish {event.__class__.__name__}"
            )

    # ========================================================================
    # Event Loop Management
    # ========================================================================

    async def start(self) -> None:
        """
        Start the event bus 24/7 event processing loop.

        This creates a background task that continuously processes events
        from the queue and dispatches them to handlers.
        """
        if self._running:
            logger.warning("EventBus already running")
            return

        self._running = True
        self._stats.started_at = datetime.utcnow()
        self._event_loop_task = asyncio.create_task(self._process_events())
        logger.info("EventBus started - processing events 24/7")

    async def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the event bus gracefully.

        Waits for the queue to drain and all handlers to complete.

        Args:
            timeout: Maximum time to wait for graceful shutdown (seconds)
        """
        if not self._running:
            logger.warning("EventBus not running")
            return

        logger.info("Stopping EventBus (draining queue: %d events)...", self._queue.qsize())
        self._running = False

        # Wait for event loop task to finish
        if self._event_loop_task:
            try:
                await asyncio.wait_for(self._event_loop_task, timeout=timeout)
                logger.info(" EventBus stopped gracefully")
            except asyncio.TimeoutError:
                logger.warning("EventBus shutdown timeout - forcing stop")
                self._event_loop_task.cancel()
                try:
                    await self._event_loop_task
                except asyncio.CancelledError:
                    pass

    async def _process_events(self) -> None:
        """
        Main 24/7 event processing loop.

        Continuously pulls events from the queue and dispatches them
        to registered handlers.
        """
        logger.info("Event processing loop started")

        while self._running or not self._queue.empty():
            try:
                # Get event from queue (with timeout to allow shutdown)
                try:
                    event = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    # No event in queue, continue loop
                    continue

                # Update stats
                self._stats.queue_size = self._queue.qsize()
                self._stats.events_processed += 1

                # Calculate events/sec
                if self._stats.started_at:
                    uptime = (datetime.utcnow() - self._stats.started_at).total_seconds()
                    if uptime > 0:
                        self._stats.events_per_second = self._stats.events_processed / uptime

                # Dispatch event to handlers
                start_time = datetime.utcnow()
                await self._dispatch_event(event)
                processing_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

                # Update average processing time
                self._stats.total_processing_time_ms += processing_time_ms
                self._stats.avg_processing_time_ms = (
                    self._stats.total_processing_time_ms / self._stats.events_processed
                )

            except Exception as e:
                logger.exception("Error in event processing loop: %s", e)
                # Continue processing despite error

        logger.info("Event processing loop stopped")

    async def _dispatch_event(self, event: Event) -> None:
        """
        Dispatch event to all registered handlers.

        Handlers are executed in parallel (using create_task) and
        errors are isolated (one handler failure doesn't affect others).

        Args:
            event: Event to dispatch
        """
        event_type = type(event)

        # Get handlers for this event type
        handlers = self._subscribers.get(event_type, [])

        # Add wildcard handlers
        all_handlers = handlers + self._wildcard_subscribers

        if not all_handlers:
            logger.debug("No handlers for event: %s", event_type.__name__)
            return

        # Execute all handlers in parallel
        tasks = []
        for handler in all_handlers:
            task = asyncio.create_task(
                self._execute_handler(handler, event), name=f"handler_{handler.__name__}"
            )
            tasks.append(task)

        # Wait for all handlers to complete (with error isolation)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_handler(self, handler: Callable, event: Event) -> None:
        """
        Execute a single event handler with error handling.

        Supports both async and sync handlers.

        Args:
            handler: Handler function to execute
            event: Event to pass to handler
        """
        try:
            # Check if handler is async
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                # Run sync handler in executor to avoid blocking
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, handler, event)

            self._stats.handlers_executed += 1

        except Exception as e:
            self._stats.handler_errors += 1
            logger.exception(
                "Error in handler %s for event %s: %s",
                handler.__name__,
                event.__class__.__name__,
                e,
            )
            # Error is isolated - other handlers will still execute

    # ========================================================================
    # Statistics & Monitoring
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """
        Get current event bus statistics.

        Returns:
            Dictionary with stats (events/sec, queue size, errors, etc.)
        """
        self._stats.queue_size = self._queue.qsize()
        return self._stats.get_stats_dict()

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._stats = EventBusStats()
        self._stats.started_at = datetime.utcnow()
        logger.info("EventBus statistics reset")

    @property
    def is_running(self) -> bool:
        """Check if event bus is running."""
        return self._running

    @property
    def queue_size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()

    def __repr__(self) -> str:
        return (
            f"EventBus(running={self._running}, "
            f"queue_size={self._queue.qsize()}, "
            f"subscribers={self.get_subscriber_count()}, "
            f"events_processed={self._stats.events_processed})"
        )
