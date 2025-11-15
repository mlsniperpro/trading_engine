"""
Email Templates for Trading Notifications

This module provides professional HTML email templates for various
notification types in the trading engine.
"""

from typing import Dict, Any, Optional
from datetime import datetime


def _base_template(title: str, content: str, priority_color: str = "#4CAF50") -> str:
    """
    Base HTML email template with consistent styling.

    Args:
        title: Email title
        content: HTML content to insert
        priority_color: Color for the header (red for critical, yellow for warning, green for info)

    Returns:
        Complete HTML email string
    """
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f4f4f4;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 20px auto;
            background-color: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{
            background-color: {priority_color};
            color: white;
            padding: 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
        }}
        .content {{
            padding: 30px;
        }}
        .metric {{
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #eee;
        }}
        .metric:last-child {{
            border-bottom: none;
        }}
        .metric-label {{
            font-weight: 600;
            color: #666;
        }}
        .metric-value {{
            color: #333;
            font-weight: 500;
        }}
        .positive {{
            color: #4CAF50;
            font-weight: 600;
        }}
        .negative {{
            color: #f44336;
            font-weight: 600;
        }}
        .footer {{
            background-color: #f8f8f8;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #666;
        }}
        .button {{
            display: inline-block;
            padding: 12px 24px;
            background-color: {priority_color};
            color: white;
            text-decoration: none;
            border-radius: 4px;
            margin: 10px 0;
        }}
        .alert-box {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 15px 0;
        }}
        .critical-box {{
            background-color: #f8d7da;
            border-left: 4px solid #dc3545;
            padding: 15px;
            margin: 15px 0;
        }}
        .info-box {{
            background-color: #d1ecf1;
            border-left: 4px solid #17a2b8;
            padding: 15px;
            margin: 15px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f8f8f8;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
        </div>
        <div class="content">
            {content}
        </div>
        <div class="footer">
            <p>Algo Trading Engine | {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
            <p>This is an automated notification. Do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
"""


def render_signal_email(signal: Dict[str, Any]) -> tuple[str, str]:
    """
    Render email for trading signal generated.

    Args:
        signal: Signal data dictionary

    Returns:
        Tuple of (subject, html_body)
    """
    symbol = signal.get('symbol', 'UNKNOWN')
    direction = signal.get('direction', 'UNKNOWN').upper()
    price = signal.get('price', 0.0)
    confluence_score = signal.get('confluence_score', 0.0)
    exchange = signal.get('exchange', 'UNKNOWN')

    # Color based on direction
    direction_color = "#4CAF50" if direction == "LONG" else "#f44336"

    content = f"""
        <h2 style="color: {direction_color};">Trading Signal: {direction} {symbol}</h2>

        <div class="info-box">
            <strong>New trading opportunity detected!</strong>
        </div>

        <div class="metric">
            <span class="metric-label">Symbol:</span>
            <span class="metric-value">{symbol}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Direction:</span>
            <span class="metric-value" style="color: {direction_color}; font-weight: bold;">{direction}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Entry Price:</span>
            <span class="metric-value">${price:,.4f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Confluence Score:</span>
            <span class="metric-value">{confluence_score:.2f}/10.0</span>
        </div>
        <div class="metric">
            <span class="metric-label">Exchange:</span>
            <span class="metric-value">{exchange}</span>
        </div>

        <h3>Signal Components:</h3>
        <ul>
            <li><strong>Primary Analyzers:</strong> {signal.get('primary_signals', 'N/A')}</li>
            <li><strong>Filter Score:</strong> {signal.get('filter_details', 'N/A')}</li>
        </ul>
    """

    subject = f"Trading Signal: {direction} {symbol} @ ${price:,.4f}"
    html_body = _base_template(subject, content, "#17a2b8")

    return subject, html_body


def render_position_opened_email(position: Dict[str, Any]) -> tuple[str, str]:
    """
    Render email for position opened.

    Args:
        position: Position data dictionary

    Returns:
        Tuple of (subject, html_body)
    """
    symbol = position.get('symbol', 'UNKNOWN')
    direction = position.get('direction', 'UNKNOWN').upper()
    entry_price = position.get('entry_price', 0.0)
    quantity = position.get('quantity', 0.0)
    position_size_usd = position.get('position_size_usd', 0.0)
    stop_loss = position.get('stop_loss', 0.0)
    exchange = position.get('exchange', 'UNKNOWN')

    direction_color = "#4CAF50" if direction == "LONG" else "#f44336"

    content = f"""
        <h2 style="color: {direction_color};">Position Opened: {direction} {symbol}</h2>

        <div class="info-box">
            <strong>New position has been opened successfully!</strong>
        </div>

        <div class="metric">
            <span class="metric-label">Symbol:</span>
            <span class="metric-value">{symbol}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Direction:</span>
            <span class="metric-value" style="color: {direction_color}; font-weight: bold;">{direction}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Entry Price:</span>
            <span class="metric-value">${entry_price:,.4f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Quantity:</span>
            <span class="metric-value">{quantity:.6f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Position Size:</span>
            <span class="metric-value">${position_size_usd:,.2f} USD</span>
        </div>
        <div class="metric">
            <span class="metric-label">Stop Loss:</span>
            <span class="metric-value">${stop_loss:,.4f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Exchange:</span>
            <span class="metric-value">{exchange}</span>
        </div>
    """

    subject = f"Position Opened: {direction} {symbol} | ${position_size_usd:,.0f}"
    html_body = _base_template(subject, content, "#4CAF50")

    return subject, html_body


def render_position_closed_email(position: Dict[str, Any]) -> tuple[str, str]:
    """
    Render email for position closed.

    Args:
        position: Position data dictionary with exit details

    Returns:
        Tuple of (subject, html_body)
    """
    symbol = position.get('symbol', 'UNKNOWN')
    direction = position.get('direction', 'UNKNOWN').upper()
    entry_price = position.get('entry_price', 0.0)
    exit_price = position.get('exit_price', 0.0)
    pnl_usd = position.get('pnl_usd', 0.0)
    pnl_pct = position.get('pnl_pct', 0.0)
    hold_time = position.get('hold_time_minutes', 0)
    exit_reason = position.get('exit_reason', 'Unknown')

    pnl_class = "positive" if pnl_usd >= 0 else "negative"
    pnl_emoji = "📈" if pnl_usd >= 0 else "📉"

    content = f"""
        <h2>Position Closed: {symbol} {pnl_emoji}</h2>

        <div class="metric">
            <span class="metric-label">Symbol:</span>
            <span class="metric-value">{symbol}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Direction:</span>
            <span class="metric-value">{direction}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Entry Price:</span>
            <span class="metric-value">${entry_price:,.4f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Exit Price:</span>
            <span class="metric-value">${exit_price:,.4f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">P&L:</span>
            <span class="metric-value {pnl_class}">${pnl_usd:+,.2f} USD ({pnl_pct:+.2f}%)</span>
        </div>
        <div class="metric">
            <span class="metric-label">Hold Time:</span>
            <span class="metric-value">{hold_time} minutes</span>
        </div>
        <div class="metric">
            <span class="metric-label">Exit Reason:</span>
            <span class="metric-value">{exit_reason}</span>
        </div>
    """

    subject = f"Position Closed: {symbol} | P&L: ${pnl_usd:+,.2f} ({pnl_pct:+.2f}%)"
    color = "#4CAF50" if pnl_usd >= 0 else "#f44336"
    html_body = _base_template(subject, content, color)

    return subject, html_body


def render_critical_error_email(error: Dict[str, Any]) -> tuple[str, str]:
    """
    Render email for critical system error.

    Args:
        error: Error data dictionary

    Returns:
        Tuple of (subject, html_body)
    """
    error_type = error.get('error_type', 'Unknown Error')
    error_message = error.get('message', 'No details available')
    component = error.get('component', 'System')
    timestamp = error.get('timestamp', datetime.utcnow().isoformat())
    stack_trace = error.get('stack_trace', '')

    content = f"""
        <h2 style="color: #dc3545;">Critical System Error</h2>

        <div class="critical-box">
            <strong>IMMEDIATE ATTENTION REQUIRED</strong><br>
            A critical error has occurred in the trading system.
        </div>

        <div class="metric">
            <span class="metric-label">Error Type:</span>
            <span class="metric-value" style="color: #dc3545; font-weight: bold;">{error_type}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Component:</span>
            <span class="metric-value">{component}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Timestamp:</span>
            <span class="metric-value">{timestamp}</span>
        </div>

        <h3>Error Details:</h3>
        <div class="critical-box">
            <code>{error_message}</code>
        </div>
    """

    if stack_trace:
        content += f"""
        <h3>Stack Trace:</h3>
        <div style="background-color: #f8f8f8; padding: 10px; overflow-x: auto; font-family: monospace; font-size: 12px;">
            <pre>{stack_trace[:500]}...</pre>
        </div>
        """

    subject = f"CRITICAL ERROR: {error_type} in {component}"
    html_body = _base_template(subject, content, "#dc3545")

    return subject, html_body


def render_order_failed_email(order: Dict[str, Any]) -> tuple[str, str]:
    """
    Render email for order failure.

    Args:
        order: Order data dictionary

    Returns:
        Tuple of (subject, html_body)
    """
    symbol = order.get('symbol', 'UNKNOWN')
    direction = order.get('direction', 'UNKNOWN').upper()
    order_type = order.get('order_type', 'UNKNOWN')
    quantity = order.get('quantity', 0.0)
    price = order.get('price', 0.0)
    error_message = order.get('error_message', 'Unknown error')
    exchange = order.get('exchange', 'UNKNOWN')

    content = f"""
        <h2 style="color: #dc3545;">Order Failed</h2>

        <div class="critical-box">
            <strong>Order execution failed!</strong><br>
            The system attempted to place an order but it was rejected.
        </div>

        <div class="metric">
            <span class="metric-label">Symbol:</span>
            <span class="metric-value">{symbol}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Direction:</span>
            <span class="metric-value">{direction}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Order Type:</span>
            <span class="metric-value">{order_type}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Quantity:</span>
            <span class="metric-value">{quantity:.6f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Price:</span>
            <span class="metric-value">${price:,.4f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Exchange:</span>
            <span class="metric-value">{exchange}</span>
        </div>

        <h3>Error Details:</h3>
        <div class="critical-box">
            <code>{error_message}</code>
        </div>

        <p><strong>Recommended Actions:</strong></p>
        <ul>
            <li>Check exchange account balance</li>
            <li>Verify API key permissions</li>
            <li>Check if symbol is tradable</li>
            <li>Review exchange rate limits</li>
        </ul>
    """

    subject = f"ORDER FAILED: {direction} {symbol} on {exchange}"
    html_body = _base_template(subject, content, "#dc3545")

    return subject, html_body


def render_batch_summary_email(priority: str, notifications: list) -> tuple[str, str]:
    """
    Render email for batched notifications summary.

    Args:
        priority: Priority level (WARNING or INFO)
        notifications: List of notification dictionaries

    Returns:
        Tuple of (subject, html_body)
    """
    count = len(notifications)

    # Group by type
    by_type: Dict[str, int] = {}
    for notif in notifications:
        notif_type = notif.get('type', 'Unknown')
        by_type[notif_type] = by_type.get(notif_type, 0) + 1

    # Build summary table
    summary_rows = ""
    for notif_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
        summary_rows += f"""
        <tr>
            <td>{notif_type}</td>
            <td style="text-align: right; font-weight: bold;">{count}</td>
        </tr>
        """

    content = f"""
        <h2>{priority.upper()} Notifications Summary</h2>

        <div class="{'alert-box' if priority == 'WARNING' else 'info-box'}">
            <strong>{count} notification(s) in this batch</strong>
        </div>

        <h3>Summary by Type:</h3>
        <table>
            <thead>
                <tr>
                    <th>Notification Type</th>
                    <th style="text-align: right;">Count</th>
                </tr>
            </thead>
            <tbody>
                {summary_rows}
            </tbody>
        </table>

        <h3>Recent Events:</h3>
    """

    # Add last 5 notifications
    for notif in notifications[-5:]:
        notif_type = notif.get('type', 'Unknown')
        notif_msg = notif.get('message', 'No details')
        notif_time = notif.get('timestamp', 'Unknown time')

        content += f"""
        <div class="metric">
            <span class="metric-label">[{notif_time}] {notif_type}:</span>
            <span class="metric-value">{notif_msg}</span>
        </div>
        """

    if len(notifications) > 5:
        content += f"<p><em>... and {len(notifications) - 5} more events</em></p>"

    subject = f"{priority.upper()} Batch: {count} notifications"
    color = "#ffc107" if priority == "WARNING" else "#17a2b8"
    html_body = _base_template(subject, content, color)

    return subject, html_body


def render_connection_lost_email(connection_info: Dict[str, Any]) -> tuple[str, str]:
    """
    Render email for market data connection loss.

    Args:
        connection_info: Connection information dictionary

    Returns:
        Tuple of (subject, html_body)
    """
    exchange = connection_info.get('exchange', 'UNKNOWN')
    market_type = connection_info.get('market_type', 'UNKNOWN')
    symbols = connection_info.get('symbols', [])
    last_heartbeat = connection_info.get('last_heartbeat', 'Unknown')
    reconnect_attempts = connection_info.get('reconnect_attempts', 0)

    content = f"""
        <h2 style="color: #dc3545;">Market Data Connection Lost</h2>

        <div class="critical-box">
            <strong>CRITICAL: Data feed disconnected!</strong><br>
            Trading system has lost connection to market data.
        </div>

        <div class="metric">
            <span class="metric-label">Exchange:</span>
            <span class="metric-value">{exchange}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Market Type:</span>
            <span class="metric-value">{market_type}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Affected Symbols:</span>
            <span class="metric-value">{', '.join(symbols) if symbols else 'All'}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Last Heartbeat:</span>
            <span class="metric-value">{last_heartbeat}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Reconnect Attempts:</span>
            <span class="metric-value">{reconnect_attempts}</span>
        </div>

        <p><strong>System Status:</strong></p>
        <ul>
            <li>Attempting automatic reconnection</li>
            <li>Open positions are being monitored</li>
            <li>New signal generation is paused</li>
        </ul>
    """

    subject = f"CRITICAL: Connection Lost to {exchange} {market_type}"
    html_body = _base_template(subject, content, "#dc3545")

    return subject, html_body
