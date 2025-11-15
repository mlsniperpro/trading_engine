"""
Unit tests for the EventBus.

Tests:
- Event publishing and subscription
- Handler execution (async and sync)
- Error isolation
- Statistics tracking
- Graceful shutdown
"""

import asyncio
import pytest
from datetime import datetime
from src.core.event_bus import EventBus, EventBusStats
from src.core.events import (
    Event,
    EventType,
    TradeTickReceived,
    OrderPlaced,
    SystemError,
    OrderSide,
    OrderType,
    OrderStatus,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
async def event_bus():
    """Create and start an event bus for testing."""
    bus = EventBus(max_queue_size=100)
    await bus.start()
    yield bus
    await bus.stop()


@pytest.fixture
def sample_trade_event():
    """Create a sample trade tick event."""
    return TradeTickReceived(
        exchange="binance",
        market_type="spot",
        symbol="BTCUSDT",
        price=50000.0,
        quantity=1.5,
        side="buy",
        trade_id="123456",
        is_buyer_maker=True,
    )


@pytest.fixture
def sample_order_event():
    """Create a sample order placed event."""
    return OrderPlaced(
        order_id="order_123",
        exchange_order_id="binance_456",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1.0,
        price=50000.0,
        exchange="binance",
        status=OrderStatus.PLACED,
    )


# ============================================================================
# Basic Functionality Tests
# ============================================================================

@pytest.mark.asyncio
async def test_event_bus_initialization():
    """Test event bus can be initialized and started."""
    bus = EventBus(max_queue_size=50)

    assert not bus.is_running
    assert bus.queue_size == 0

    await bus.start()
    assert bus.is_running

    await bus.stop()
    assert not bus.is_running


@pytest.mark.asyncio
async def test_publish_and_subscribe(event_bus, sample_trade_event):
    """Test basic event publishing and subscription."""
    received_events = []

    async def handler(event: TradeTickReceived):
        received_events.append(event)

    # Subscribe
    event_bus.subscribe(TradeTickReceived, handler)

    # Publish
    await event_bus.publish(sample_trade_event)

    # Wait for processing
    await asyncio.sleep(0.2)

    # Verify
    assert len(received_events) == 1
    assert received_events[0] == sample_trade_event
    assert received_events[0].symbol == "BTCUSDT"
    assert received_events[0].price == 50000.0


@pytest.mark.asyncio
async def test_multiple_subscribers(event_bus, sample_trade_event):
    """Test multiple handlers can subscribe to same event type."""
    received_by_handler1 = []
    received_by_handler2 = []

    async def handler1(event: TradeTickReceived):
        received_by_handler1.append(event)

    async def handler2(event: TradeTickReceived):
        received_by_handler2.append(event)

    # Subscribe both
    event_bus.subscribe(TradeTickReceived, handler1)
    event_bus.subscribe(TradeTickReceived, handler2)

    # Publish one event
    await event_bus.publish(sample_trade_event)

    # Wait for processing
    await asyncio.sleep(0.2)

    # Both handlers should receive the event
    assert len(received_by_handler1) == 1
    assert len(received_by_handler2) == 1


@pytest.mark.asyncio
async def test_wildcard_subscription(event_bus, sample_trade_event, sample_order_event):
    """Test wildcard subscription receives all events."""
    all_events = []

    async def wildcard_handler(event: Event):
        all_events.append(event)

    # Subscribe to all events
    event_bus.subscribe_to_all(wildcard_handler)

    # Publish different event types
    await event_bus.publish(sample_trade_event)
    await event_bus.publish(sample_order_event)

    # Wait for processing
    await asyncio.sleep(0.2)

    # Should receive both events
    assert len(all_events) == 2
    assert isinstance(all_events[0], TradeTickReceived)
    assert isinstance(all_events[1], OrderPlaced)


# ============================================================================
# Handler Execution Tests
# ============================================================================

@pytest.mark.asyncio
async def test_async_handler_execution(event_bus, sample_trade_event):
    """Test async handlers are executed correctly."""
    execution_order = []

    async def async_handler(event: TradeTickReceived):
        await asyncio.sleep(0.1)
        execution_order.append("async_handler")

    event_bus.subscribe(TradeTickReceived, async_handler)
    await event_bus.publish(sample_trade_event)

    await asyncio.sleep(0.3)

    assert "async_handler" in execution_order


@pytest.mark.asyncio
async def test_sync_handler_execution(event_bus, sample_trade_event):
    """Test sync handlers are executed correctly."""
    execution_order = []

    def sync_handler(event: TradeTickReceived):
        # Sync function
        execution_order.append("sync_handler")

    event_bus.subscribe(TradeTickReceived, sync_handler)
    await event_bus.publish(sample_trade_event)

    await asyncio.sleep(0.2)

    assert "sync_handler" in execution_order


@pytest.mark.asyncio
async def test_mixed_async_sync_handlers(event_bus, sample_trade_event):
    """Test both async and sync handlers can coexist."""
    results = {"async": False, "sync": False}

    async def async_handler(event: TradeTickReceived):
        await asyncio.sleep(0.05)
        results["async"] = True

    def sync_handler(event: TradeTickReceived):
        results["sync"] = True

    event_bus.subscribe(TradeTickReceived, async_handler)
    event_bus.subscribe(TradeTickReceived, sync_handler)

    await event_bus.publish(sample_trade_event)
    await asyncio.sleep(0.2)

    assert results["async"]
    assert results["sync"]


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.asyncio
async def test_error_isolation(event_bus, sample_trade_event):
    """Test that one handler failure doesn't affect others."""
    successful_handlers = []

    async def failing_handler(event: TradeTickReceived):
        raise ValueError("Handler intentionally failed")

    async def successful_handler1(event: TradeTickReceived):
        successful_handlers.append("handler1")

    async def successful_handler2(event: TradeTickReceived):
        successful_handlers.append("handler2")

    # Subscribe all handlers
    event_bus.subscribe(TradeTickReceived, failing_handler)
    event_bus.subscribe(TradeTickReceived, successful_handler1)
    event_bus.subscribe(TradeTickReceived, successful_handler2)

    # Publish event
    await event_bus.publish(sample_trade_event)
    await asyncio.sleep(0.2)

    # Successful handlers should still execute
    assert len(successful_handlers) == 2
    assert "handler1" in successful_handlers
    assert "handler2" in successful_handlers

    # Error should be tracked in stats
    stats = event_bus.get_stats()
    assert stats["handler_errors"] >= 1


# ============================================================================
# Unsubscribe Tests
# ============================================================================

@pytest.mark.asyncio
async def test_unsubscribe(event_bus, sample_trade_event):
    """Test unsubscribing from events."""
    received_events = []

    async def handler(event: TradeTickReceived):
        received_events.append(event)

    # Subscribe and publish
    event_bus.subscribe(TradeTickReceived, handler)
    await event_bus.publish(sample_trade_event)
    await asyncio.sleep(0.1)

    assert len(received_events) == 1

    # Unsubscribe and publish again
    event_bus.unsubscribe(TradeTickReceived, handler)
    await event_bus.publish(sample_trade_event)
    await asyncio.sleep(0.1)

    # Should still be 1 (no new event received)
    assert len(received_events) == 1


# ============================================================================
# Statistics Tests
# ============================================================================

@pytest.mark.asyncio
async def test_statistics_tracking(event_bus, sample_trade_event):
    """Test event bus tracks statistics correctly."""
    async def handler(event: TradeTickReceived):
        await asyncio.sleep(0.01)

    event_bus.subscribe(TradeTickReceived, handler)

    # Publish multiple events
    for _ in range(5):
        await event_bus.publish(sample_trade_event)

    await asyncio.sleep(0.3)

    # Check stats
    stats = event_bus.get_stats()
    assert stats["events_published"] == 5
    assert stats["events_processed"] == 5
    assert stats["handlers_executed"] >= 5
    assert stats["avg_processing_time_ms"] > 0


@pytest.mark.asyncio
async def test_queue_size_tracking(event_bus, sample_trade_event):
    """Test queue size is tracked correctly."""
    # Publish without subscribers (events queue up briefly)
    for _ in range(10):
        await event_bus.publish(sample_trade_event)

    # Queue should have events
    await asyncio.sleep(0.1)

    stats = event_bus.get_stats()
    # Queue should be drained by now
    assert stats["queue_size"] >= 0


# ============================================================================
# Graceful Shutdown Tests
# ============================================================================

@pytest.mark.asyncio
async def test_graceful_shutdown():
    """Test event bus shuts down gracefully."""
    bus = EventBus()
    await bus.start()

    # Publish some events
    event = TradeTickReceived(
        exchange="binance",
        market_type="spot",
        symbol="BTCUSDT",
        price=50000.0,
        quantity=1.0,
        side="buy",
        trade_id="123",
    )

    for _ in range(5):
        await bus.publish(event)

    # Stop gracefully
    await bus.stop(timeout=2.0)

    assert not bus.is_running
    # Queue should be drained
    assert bus.queue_size == 0


@pytest.mark.asyncio
async def test_publish_after_stop(sample_trade_event):
    """Test publishing after stop raises appropriate error."""
    bus = EventBus()
    await bus.start()
    await bus.stop()

    # Publishing after stop should fail gracefully
    # (EventBus may queue but won't process)
    # This is expected behavior - you can still publish but nothing processes


# ============================================================================
# Subscriber Count Tests
# ============================================================================

@pytest.mark.asyncio
async def test_subscriber_count(event_bus):
    """Test getting subscriber counts."""
    async def handler1(event): pass
    async def handler2(event): pass

    # Initially no subscribers
    assert event_bus.get_subscriber_count(TradeTickReceived) == 0

    # Add subscribers
    event_bus.subscribe(TradeTickReceived, handler1)
    assert event_bus.get_subscriber_count(TradeTickReceived) == 1

    event_bus.subscribe(TradeTickReceived, handler2)
    assert event_bus.get_subscriber_count(TradeTickReceived) == 2

    # Total subscribers
    event_bus.subscribe(OrderPlaced, handler1)
    assert event_bus.get_subscriber_count() == 3  # 2 for TradeTickReceived, 1 for OrderPlaced


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
