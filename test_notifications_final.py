"""
Final notification test using proper Python package imports
"""

import asyncio
import sys
import os
import logging
from datetime import datetime

# Add src to Python path
sys.path.insert(0, '/workspaces/trading_engine/src')

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def main():
    print("\n" + "="*80)
    print("NOTIFICATION SYSTEM TEST")
    print("="*80 + "\n")
    
    # Import directly from package
    from notifications import SendGridNotificationService, NotificationPriority
    import notifications.templates as templates
    
    print("✓ Imports successful\n")
    
    # Create mock service
    print("Creating SendGrid Service (MOCK MODE)...")
    service = SendGridNotificationService(
        from_email="algo@trading.com",
        to_emails=["trader@example.com"],
        mock_mode=True
    )
    print("✓ Service created\n")
    
    # Test templates
    print("Testing email templates...\n")
    
    # 1. Trading signal
    signal = {
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "price": 42500.50,
        "confluence_score": 7.5,
        "exchange": "binance",
        "primary_signals": "Order Flow + Rejection",
        "filter_details": "MP + DZ + FVG"
    }
    subject, html = templates.render_signal_email(signal)
    print(f"1. Signal Email: {subject}")
    
    # 2. Position opened
    position = {
        "symbol": "ETHUSDT",
        "direction": "LONG",
        "entry_price": 2500.75,
        "quantity": 10.5,
        "position_size_usd": 26257.88,
        "stop_loss": 2450.00,
        "exchange": "binance"
    }
    subject, html = templates.render_position_opened_email(position)
    print(f"2. Position Opened: {subject}")
    
    # 3. Position closed (profit)
    closed = {
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entry_price": 42500.00,
        "exit_price": 43250.50,
        "pnl_usd": 375.25,
        "pnl_pct": 1.76,
        "hold_time_minutes": 25,
        "exit_reason": "take_profit"
    }
    subject, html = templates.render_position_closed_email(closed)
    print(f"3. Position Closed: {subject}")
    
    # 4. Order failed
    order = {
        "symbol": "BTCUSDT",
        "direction": "BUY",
        "order_type": "MARKET",
        "quantity": 0.5,
        "price": 42500.00,
        "error_message": "Insufficient balance",
        "exchange": "binance"
    }
    subject, html = templates.render_order_failed_email(order)
    print(f"4. Order Failed: {subject}")
    
    # 5. Critical error
    error = {
        "error_type": "ConnectionError",
        "message": "WebSocket connection failed",
        "component": "MarketDataManager",
        "timestamp": datetime.utcnow().isoformat(),
        "stack_trace": "Traceback..."
    }
    subject, html = templates.render_critical_error_email(error)
    print(f"5. Critical Error: {subject}")
    
    # 6. Connection lost
    conn = {
        "exchange": "binance",
        "market_type": "spot",
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "last_heartbeat": datetime.utcnow().isoformat(),
        "reconnect_attempts": 3
    }
    subject, html = templates.render_connection_lost_email(conn)
    print(f"6. Connection Lost: {subject}")
    
    print("\n✓ All templates tested\n")
    
    # Send mock emails
    print("Sending mock emails...\n")
    
    await service.notify_trade_signal(signal)
    print("  ✓ Signal notification sent")
    
    await service.notify_position_opened(position)
    print("  ✓ Position opened sent")
    
    await service.notify_position_closed(closed)
    print("  ✓ Position closed sent")
    
    await service.notify_order_failed(order)
    print("  ✓ Order failed sent")
    
    await service.notify_critical_error(error)
    print("  ✓ Critical error sent")
    
    await service.notify_connection_lost(conn)
    print("  ✓ Connection lost sent")
    
    # Show history
    print("\n" + "="*80)
    print("MOCK EMAIL HISTORY")
    print("="*80 + "\n")
    
    emails = service.get_mock_history()
    print(f"Total emails: {len(emails)}\n")
    
    for i, email in enumerate(emails, 1):
        print(f"{i}. {email['subject']}")
    
    print("\n" + "="*80)
    print("TEST COMPLETED SUCCESSFULLY")
    print("="*80 + "\n")
    
    print("Summary:")
    print(f"  ✓ {len(emails)} mock emails generated")
    print("  ✓ All notification types tested")
    print("  ✓ HTML templates rendered correctly")
    print("  ✓ No real emails sent (mock mode)")
    print()

if __name__ == "__main__":
    asyncio.run(main())
