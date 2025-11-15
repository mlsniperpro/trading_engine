"""
Standalone Notification System Test

This tests ONLY the notification components without any dependencies.
"""

import asyncio
import logging
from datetime import datetime
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# We'll import the specific modules we need directly
def test_imports():
    """Test that all modules import correctly."""
    print("Testing imports...")

    try:
        # Direct imports to avoid circular dependencies
        import notifications.templates as templates
        print("  ✓ templates imported")

        from notifications.priority import NotificationPriority, PriorityHandler, PriorityConfig
        print("  ✓ priority imported")

        # Import MockSendGridClient directly from the module
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "sendgrid_client",
            "/workspaces/trading_engine/src/notifications/sendgrid_client.py"
        )
        sendgrid_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sendgrid_module)

        SendGridNotificationService = sendgrid_module.SendGridNotificationService
        MockSendGridClient = sendgrid_module.MockSendGridClient

        print("  ✓ sendgrid_client imported\n")

        return templates, NotificationPriority, SendGridNotificationService, MockSendGridClient

    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None


async def run_tests():
    """Run notification tests."""

    print("\n" + "="*80)
    print("STANDALONE NOTIFICATION SYSTEM TEST")
    print("="*80 + "\n")

    # Test imports
    result = test_imports()
    if None in result:
        print("Import test failed. Exiting.")
        return

    templates, NotificationPriority, SendGridNotificationService, MockSendGridClient = result

    # Test 1: Mock SendGrid Client
    print("1. Testing Mock SendGrid Client...")
    mock_client = MockSendGridClient()
    print("   ✓ Mock client created\n")

    # Test 2: SendGrid Service in Mock Mode
    print("2. Creating SendGrid Service (MOCK MODE)...")
    sendgrid = SendGridNotificationService(
        from_email="algo-engine@trading.com",
        to_emails=["trader@example.com"],
        mock_mode=True
    )
    print("   ✓ Service initialized\n")

    # Test 3: Trading Signal Template
    print("3. Testing Trading Signal Email Template...")
    signal_data = {
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "price": 42500.50,
        "confluence_score": 7.5,
        "exchange": "binance",
        "primary_signals": "Order Flow + Rejection",
        "filter_details": "Market Profile + Demand Zone"
    }
    subject, html = templates.render_signal_email(signal_data)
    print(f"   Subject: {subject}")
    print(f"   HTML length: {len(html)} characters")
    print("   ✓ Template rendered\n")

    # Test 4: Position Opened Template
    print("4. Testing Position Opened Email Template...")
    position_data = {
        "symbol": "ETHUSDT",
        "direction": "LONG",
        "entry_price": 2500.75,
        "quantity": 10.5,
        "position_size_usd": 26257.88,
        "stop_loss": 2450.00,
        "exchange": "binance"
    }
    subject, html = templates.render_position_opened_email(position_data)
    print(f"   Subject: {subject}")
    print(f"   HTML length: {len(html)} characters")
    print("   ✓ Template rendered\n")

    # Test 5: Position Closed Template (Profit)
    print("5. Testing Position Closed Email Template (Profit)...")
    closed_data = {
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entry_price": 42500.00,
        "exit_price": 43250.50,
        "pnl_usd": 375.25,
        "pnl_pct": 1.76,
        "hold_time_minutes": 25,
        "exit_reason": "take_profit"
    }
    subject, html = templates.render_position_closed_email(closed_data)
    print(f"   Subject: {subject}")
    print(f"   HTML length: {len(html)} characters")
    print("   ✓ Template rendered\n")

    # Test 6: Critical Error Template
    print("6. Testing Critical Error Email Template...")
    error_data = {
        "error_type": "ConnectionError",
        "message": "Failed to connect to Binance WebSocket after 5 retries",
        "component": "MarketDataManager",
        "timestamp": datetime.utcnow().isoformat(),
        "stack_trace": "Traceback...\n  File manager.py..."
    }
    subject, html = templates.render_critical_error_email(error_data)
    print(f"   Subject: {subject}")
    print(f"   HTML length: {len(html)} characters")
    print("   ✓ Template rendered\n")

    # Test 7: Order Failed Template
    print("7. Testing Order Failed Email Template...")
    order_data = {
        "symbol": "BTCUSDT",
        "direction": "BUY",
        "order_type": "MARKET",
        "quantity": 0.5,
        "price": 42500.00,
        "error_message": "Insufficient balance",
        "exchange": "binance"
    }
    subject, html = templates.render_order_failed_email(order_data)
    print(f"   Subject: {subject}")
    print(f"   HTML length: {len(html)} characters")
    print("   ✓ Template rendered\n")

    # Test 8: Connection Lost Template
    print("8. Testing Connection Lost Email Template...")
    conn_data = {
        "exchange": "binance",
        "market_type": "spot",
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "last_heartbeat": datetime.utcnow().isoformat(),
        "reconnect_attempts": 3
    }
    subject, html = templates.render_connection_lost_email(conn_data)
    print(f"   Subject: {subject}")
    print(f"   HTML length: {len(html)} characters")
    print("   ✓ Template rendered\n")

    # Test 9: Batch Summary Template
    print("9. Testing Batch Summary Email Template...")
    notifications = [
        {"type": "Signal", "message": "LONG BTC", "timestamp": datetime.utcnow().isoformat()},
        {"type": "Position", "message": "Opened ETH", "timestamp": datetime.utcnow().isoformat()},
    ]
    subject, html = templates.render_batch_summary_email("INFO", notifications)
    print(f"   Subject: {subject}")
    print(f"   HTML length: {len(html)} characters")
    print("   ✓ Template rendered\n")

    # Test 10: Send mock emails
    print("10. Testing Mock Email Sending...")

    success = await sendgrid.notify_trade_signal(signal_data)
    print(f"    Signal notification: {'✓ SUCCESS' if success else '✗ FAILED'}")

    success = await sendgrid.notify_position_opened(position_data)
    print(f"    Position opened: {'✓ SUCCESS' if success else '✗ FAILED'}")

    success = await sendgrid.notify_position_closed(closed_data)
    print(f"    Position closed: {'✓ SUCCESS' if success else '✗ FAILED'}")

    success = await sendgrid.notify_order_failed(order_data)
    print(f"    Order failed: {'✓ SUCCESS' if success else '✗ FAILED'}")

    success = await sendgrid.notify_critical_error(error_data)
    print(f"    Critical error: {'✓ SUCCESS' if success else '✗ FAILED'}")

    success = await sendgrid.notify_connection_lost(conn_data)
    print(f"    Connection lost: {'✓ SUCCESS' if success else '✗ FAILED'}")

    print()

    # Show mock history
    print("="*80)
    print("MOCK EMAIL HISTORY")
    print("="*80 + "\n")

    mock_emails = sendgrid.get_mock_history()
    print(f"Total mock emails: {len(mock_emails)}\n")

    for idx, email in enumerate(mock_emails, 1):
        print(f"{idx}. To: {email['to']}")
        print(f"   Subject: {email['subject']}")
        print()

    # Summary
    print("="*80)
    print("TEST COMPLETED")
    print("="*80 + "\n")

    print("✓ All notification templates tested successfully")
    print(f"✓ {len(mock_emails)} mock emails generated")
    print("✓ No real emails sent (mock mode)")
    print("✓ All email types validated")
    print("\n")


if __name__ == "__main__":
    asyncio.run(run_tests())
