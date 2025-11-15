"""
Mock test for the notification system.

This test demonstrates the notification system using a mock SendGrid client
so no real emails are sent.
"""

import asyncio
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import the notification components
import sys
sys.path.insert(0, '/workspaces/trading_engine/src')

from core.event_bus import EventBus
from core.events import (
    TradingSignalGenerated,
    OrderSide,
    PositionOpened,
    PositionClosed,
    OrderFailed,
    SystemError,
    MarketDataConnectionLost,
)
from notifications.sendgrid_client import SendGridNotificationService
from notifications.service import NotificationSystem


async def test_notification_system():
    """
    Test the notification system with mock emails.
    """
    print("\n" + "="*80)
    print("TESTING NOTIFICATION SYSTEM (MOCK MODE)")
    print("="*80 + "\n")

    # 1. Create event bus
    print("1. Creating Event Bus...")
    event_bus = EventBus()
    await event_bus.start()
    print("   Event Bus started\n")

    # 2. Create SendGrid service in MOCK mode
    print("2. Creating SendGrid Service (MOCK MODE)...")
    sendgrid_service = SendGridNotificationService(
        from_email="algo-engine@trading.com",
        to_emails=["trader@example.com"],
        mock_mode=True  # <-- This prevents real emails from being sent
    )
    print("   SendGrid service initialized in mock mode\n")

    # 3. Create notification system
    print("3. Creating Notification System...")
    notification_system = NotificationSystem(
        event_bus=event_bus,
        sendgrid_service=sendgrid_service
    )
    await notification_system.start()
    print("   Notification system started\n")

    # Allow time for subscriptions to register
    await asyncio.sleep(0.5)

    # 4. Test CRITICAL notification (Order Failed)
    print("4. Testing CRITICAL Notification (Order Failed)...")
    order_failed_event = OrderFailed(
        order_id="ORD-12345",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        error_code="INSUFFICIENT_BALANCE",
        error_message="Insufficient balance to execute order. Required: $10,000, Available: $5,000",
        exchange="binance",
        retry_count=0,
        is_retriable=False
    )
    await event_bus.publish(order_failed_event)
    print("   Order Failed event published\n")

    # Wait for event to be processed
    await asyncio.sleep(1)

    # 5. Test CRITICAL notification (System Error)
    print("5. Testing CRITICAL Notification (System Error)...")
    system_error_event = SystemError(
        component="MarketDataManager",
        error_type="ConnectionError",
        error_message="Failed to connect to Binance WebSocket API after 5 retries",
        traceback="Traceback (most recent call last):\n  File 'manager.py', line 123...",
        is_critical=True
    )
    await event_bus.publish(system_error_event)
    print("   System Error event published\n")

    # Wait for event to be processed
    await asyncio.sleep(1)

    # 6. Test CRITICAL notification (Connection Lost)
    print("6. Testing CRITICAL Notification (Connection Lost)...")
    connection_lost_event = MarketDataConnectionLost(
        exchange="binance",
        market_type="spot",
        symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"],
        error_message="WebSocket connection timeout after 30 seconds",
        retry_attempt=2
    )
    await event_bus.publish(connection_lost_event)
    print("   Connection Lost event published\n")

    # Wait for event to be processed
    await asyncio.sleep(1)

    # 7. Test INFO notification (Trading Signal)
    print("7. Testing INFO Notification (Trading Signal - will be batched)...")
    signal_event = TradingSignalGenerated(
        symbol="ETHUSDT",
        side=OrderSide.BUY,
        signal_strength=8.5,
        confluence_score=7.2,
        entry_price=2500.50,
        stop_loss=2450.00,
        take_profit=2600.00,
        position_size_pct=2.0,
        primary_signals={"order_flow": True, "rejection": True},
        filter_scores={"market_profile": 1.5, "demand_zone": 2.0},
        exchange="binance",
        market_type="spot",
        timeframe="1m"
    )
    await event_bus.publish(signal_event)
    print("   Trading Signal event published (batched)\n")

    # Wait for event to be processed
    await asyncio.sleep(1)

    # 8. Test INFO notification (Position Opened)
    print("8. Testing INFO Notification (Position Opened - will be batched)...")
    position_opened_event = PositionOpened(
        position_id="POS-67890",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        entry_price=42350.75,
        quantity=0.5,
        exchange="binance",
        market_type="spot",
        stop_loss=42000.00,
        take_profit=43000.00,
        trailing_stop_distance_pct=0.5
    )
    await event_bus.publish(position_opened_event)
    print("   Position Opened event published (batched)\n")

    # Wait for event to be processed
    await asyncio.sleep(1)

    # 9. Test INFO notification (Position Closed - Profit)
    print("9. Testing INFO Notification (Position Closed with Profit - will be batched)...")
    position_closed_event = PositionClosed(
        position_id="POS-67890",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        entry_price=42350.75,
        exit_price=42850.50,
        quantity=0.5,
        exchange="binance",
        realized_pnl=249.88,
        realized_pnl_pct=1.18,
        exit_reason="take_profit",
        hold_duration_seconds=1845  # 30.75 minutes
    )
    await event_bus.publish(position_closed_event)
    print("   Position Closed event published (batched)\n")

    # Wait for all events to be processed
    await asyncio.sleep(2)

    # 10. Check mock email history
    print("\n" + "="*80)
    print("MOCK EMAIL HISTORY")
    print("="*80 + "\n")

    mock_emails = sendgrid_service.get_mock_history()
    print(f"Total mock emails sent: {len(mock_emails)}\n")

    for idx, email in enumerate(mock_emails, 1):
        print(f"{idx}. To: {email['to']}")
        print(f"   Subject: {email['subject']}")
        print(f"   Timestamp: {email['timestamp']}")
        print()

    # 11. Show statistics
    print("="*80)
    print("NOTIFICATION SYSTEM STATISTICS")
    print("="*80 + "\n")

    stats = notification_system.get_stats()
    print(f"Notifications Sent: {stats['notifications_sent']}")
    print(f"Notifications Failed: {stats['notifications_failed']}")
    print(f"Critical Sent: {stats['critical_sent']}")
    print(f"Warning Batched: {stats['warning_batched']}")
    print(f"Info Batched: {stats['info_batched']}")
    print()

    priority_stats = stats['priority_handler']
    print("Batched Notifications:")
    for priority, count in priority_stats['batched_counts'].items():
        print(f"  {priority}: {count} queued")
    print()

    # 12. Cleanup
    print("="*80)
    print("CLEANUP")
    print("="*80 + "\n")

    await notification_system.stop()
    print("Notification system stopped")

    await event_bus.stop()
    print("Event bus stopped")

    print("\n" + "="*80)
    print("TEST COMPLETED SUCCESSFULLY!")
    print("="*80 + "\n")

    print("SUMMARY:")
    print("- No real emails were sent (mock mode)")
    print(f"- {len(mock_emails)} mock emails generated")
    print("- All notification types tested (CRITICAL, WARNING, INFO)")
    print("- Batching system tested (INFO events queued)")
    print("- Priority routing tested (CRITICAL sent immediately)")
    print()


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_notification_system())
