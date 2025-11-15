"""
Data Formatting Utilities

Provides consistent formatting for:
- Price and volume display
- Timestamp formatting
- Number formatting with units
- JSON serialization
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from decimal import Decimal, ROUND_HALF_UP
import re


class PriceFormatter:
    """Formats prices with appropriate precision."""
    
    @staticmethod
    def format_price(price: float, pair: str = None, precision: int = None) -> str:
        """
        Format price with appropriate precision based on pair.
        
        Args:
            price: Price value to format
            pair: Trading pair (for determining precision)
            precision: Override precision
            
        Returns:
            Formatted price string
        """
        if precision is None:
            precision = PriceFormatter._get_price_precision(pair, price)
        
        # Use Decimal for precise formatting
        price_decimal = Decimal(str(price))
        format_str = f"{{:.{precision}f}}"
        
        return format_str.format(float(price_decimal))
    
    @staticmethod
    def _get_price_precision(pair: str, price: float) -> int:
        """Determine appropriate price precision."""
        if pair is None:
            return 8 if price < 1 else 4 if price < 100 else 2
        
        pair_upper = pair.upper()
        
        # Forex pairs
        if any(currency in pair_upper for currency in ['JPY', 'KRW']):
            return 3
        elif any(pair_upper.endswith(currency) for currency in ['USD', 'EUR', 'GBP']):
            return 5
        
        # Crypto pairs
        if price < 0.001:
            return 8
        elif price < 0.1:
            return 6
        elif price < 10:
            return 4
        else:
            return 2


class VolumeFormatter:
    """Formats volume with appropriate units."""
    
    @staticmethod
    def format_volume(volume: float, base_currency: str = None) -> str:
        """
        Format volume with K/M/B units.
        
        Args:
            volume: Volume value
            base_currency: Base currency for context
            
        Returns:
            Formatted volume string
        """
        if volume == 0:
            return "0"
        
        abs_volume = abs(volume)
        sign = "-" if volume < 0 else ""
        
        if abs_volume >= 1_000_000_000:
            return f"{sign}{abs_volume/1_000_000_000:.2f}B"
        elif abs_volume >= 1_000_000:
            return f"{sign}{abs_volume/1_000_000:.2f}M"
        elif abs_volume >= 1_000:
            return f"{sign}{abs_volume/1_000:.2f}K"
        else:
            return f"{sign}{abs_volume:.2f}"


class TimestampFormatter:
    """Formats timestamps consistently."""
    
    @staticmethod
    def format_timestamp(timestamp: Union[datetime, int, float], 
                        format_type: str = "iso") -> str:
        """
        Format timestamp in various formats.
        
        Args:
            timestamp: Timestamp to format
            format_type: Format type (iso, human, trading)
            
        Returns:
            Formatted timestamp string
        """
        # Convert to datetime if needed
        if isinstance(timestamp, (int, float)):
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        elif isinstance(timestamp, datetime):
            dt = timestamp.astimezone(timezone.utc) if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
        else:
            return str(timestamp)
        
        if format_type == "iso":
            return dt.isoformat()
        elif format_type == "human":
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        elif format_type == "trading":
            return dt.strftime("%H:%M:%S")
        elif format_type == "date":
            return dt.strftime("%Y-%m-%d")
        else:
            return dt.strftime(format_type)  # Custom format string


class NumberFormatter:
    """General number formatting utilities."""
    
    @staticmethod
    def format_percentage(value: float, precision: int = 2) -> str:
        """Format percentage with specified precision."""
        return f"{value:.{precision}f}%"
    
    @staticmethod
    def format_basis_points(value: float) -> str:
        """Format value as basis points."""
        return f"{value:.1f}bp"
    
    @staticmethod
    def format_pnl(pnl: float, currency: str = "USD") -> str:
        """Format P&L with color coding info."""
        sign = "+" if pnl > 0 else ""
        color = "green" if pnl > 0 else "red" if pnl < 0 else "gray"
        
        formatted_value = PriceFormatter.format_price(abs(pnl), precision=2)
        return f"{sign}{formatted_value} {currency}"
    
    @staticmethod
    def format_scientific(value: float, precision: int = 3) -> str:
        """Format number in scientific notation."""
        return f"{value:.{precision}e}"
    
    @staticmethod
    def format_with_commas(value: Union[int, float]) -> str:
        """Format number with comma separators."""
        return f"{value:,}"


class JSONFormatter:
    """JSON formatting utilities."""
    
    @staticmethod
    def format_json(data: Any, indent: int = 2, sort_keys: bool = True) -> str:
        """Format data as JSON string."""
        return json.dumps(
            data, 
            indent=indent, 
            sort_keys=sort_keys, 
            default=JSONFormatter._json_serializer,
            ensure_ascii=False
        )
    
    @staticmethod
    def _json_serializer(obj: Any) -> Any:
        """Custom JSON serializer for non-standard types."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return str(obj)
    
    @staticmethod
    def minify_json(json_str: str) -> str:
        """Remove whitespace from JSON string."""
        return json.dumps(json.loads(json_str), separators=(',', ':'))


class TableFormatter:
    """Formats data in table format."""
    
    @staticmethod
    def format_table(headers: list, rows: list, max_width: int = 20) -> str:
        """
        Format data as ASCII table.
        
        Args:
            headers: List of column headers
            rows: List of row data
            max_width: Maximum column width
            
        Returns:
            Formatted table string
        """
        if not headers or not rows:
            return ""
        
        # Calculate column widths
        col_widths = []
        for i, header in enumerate(headers):
            width = len(str(header))
            for row in rows:
                if i < len(row):
                    width = max(width, len(str(row[i])))
            col_widths.append(min(width, max_width))
        
        # Format header
        header_row = " | ".join(str(headers[i]).ljust(col_widths[i]) for i in range(len(headers)))
        separator = "-+-".join("-" * width for width in col_widths)
        
        # Format rows
        formatted_rows = []
        for row in rows:
            formatted_row = " | ".join(
                str(row[i] if i < len(row) else "").ljust(col_widths[i])[:col_widths[i]]
                for i in range(len(headers))
            )
            formatted_rows.append(formatted_row)
        
        return "\n".join([header_row, separator] + formatted_rows)


class OrderFormatter:
    """Formats trading order information."""
    
    @staticmethod
    def format_order(order_data: Dict[str, Any]) -> str:
        """Format order for display."""
        side = order_data.get('side', 'UNKNOWN').upper()
        pair = order_data.get('pair', 'UNKNOWN')
        size = order_data.get('size', 0)
        price = order_data.get('price', 0)
        order_type = order_data.get('type', 'MARKET').upper()
        
        formatted_size = VolumeFormatter.format_volume(size)
        formatted_price = PriceFormatter.format_price(price, pair)
        
        if order_type == 'MARKET':
            return f"{side} {formatted_size} {pair} @ MARKET"
        else:
            return f"{side} {formatted_size} {pair} @ {formatted_price}"
    
    @staticmethod
    def format_position(position_data: Dict[str, Any]) -> str:
        """Format position for display."""
        pair = position_data.get('pair', 'UNKNOWN')
        size = position_data.get('size', 0)
        entry_price = position_data.get('entry_price', 0)
        current_price = position_data.get('current_price', 0)
        unrealized_pnl = position_data.get('unrealized_pnl', 0)
        
        side = "LONG" if size > 0 else "SHORT" if size < 0 else "FLAT"
        
        formatted_size = VolumeFormatter.format_volume(abs(size))
        formatted_entry = PriceFormatter.format_price(entry_price, pair)
        formatted_current = PriceFormatter.format_price(current_price, pair)
        formatted_pnl = NumberFormatter.format_pnl(unrealized_pnl)
        
        return f"{pair} {side} {formatted_size} @ {formatted_entry} (Mark: {formatted_current}) PnL: {formatted_pnl}"


class MetricsFormatter:
    """Formats performance metrics."""
    
    @staticmethod
    def format_performance_metrics(metrics: Dict[str, float]) -> str:
        """Format trading performance metrics."""
        lines = []
        
        # P&L metrics
        if 'total_pnl' in metrics:
            lines.append(f"Total P&L: {NumberFormatter.format_pnl(metrics['total_pnl'])}")
        
        if 'win_rate' in metrics:
            lines.append(f"Win Rate: {NumberFormatter.format_percentage(metrics['win_rate'] * 100)}")
        
        if 'sharpe_ratio' in metrics:
            lines.append(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        
        if 'max_drawdown' in metrics:
            lines.append(f"Max Drawdown: {NumberFormatter.format_percentage(metrics['max_drawdown'] * 100)}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_system_metrics(metrics: Dict[str, Any]) -> str:
        """Format system performance metrics."""
        lines = []
        
        if 'cpu_usage' in metrics:
            lines.append(f"CPU: {NumberFormatter.format_percentage(metrics['cpu_usage'])}")
        
        if 'memory_usage' in metrics:
            lines.append(f"Memory: {VolumeFormatter.format_volume(metrics['memory_usage'])}B")
        
        if 'latency_p99' in metrics:
            lines.append(f"Latency P99: {metrics['latency_p99']:.2f}ms")
        
        return "\n".join(lines)


# Convenience functions for common formatting tasks
def format_currency(amount: float, currency: str = "USD", precision: int = 2) -> str:
    """Format currency amount."""
    return f"{amount:.{precision}f} {currency}"


def format_spread(bid: float, ask: float, pair: str = None) -> str:
    """Format bid-ask spread."""
    spread = ask - bid
    spread_bps = (spread / ((bid + ask) / 2)) * 10000
    
    formatted_spread = PriceFormatter.format_price(spread, pair)
    return f"{formatted_spread} ({spread_bps:.1f}bp)"


def format_market_data(data: Dict[str, Any]) -> str:
    """Format market data summary."""
    pair = data.get('pair', 'UNKNOWN')
    bid = data.get('bid', 0)
    ask = data.get('ask', 0)
    volume_24h = data.get('volume_24h', 0)
    
    mid_price = (bid + ask) / 2 if bid and ask else 0
    spread = format_spread(bid, ask, pair)
    
    lines = [
        f"Pair: {pair}",
        f"Bid: {PriceFormatter.format_price(bid, pair)}",
        f"Ask: {PriceFormatter.format_price(ask, pair)}",
        f"Mid: {PriceFormatter.format_price(mid_price, pair)}",
        f"Spread: {spread}",
        f"24h Volume: {VolumeFormatter.format_volume(volume_24h)}"
    ]
    
    return "\n".join(lines)