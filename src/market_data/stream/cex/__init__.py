"""
CEX (Centralized Exchange) stream handlers.

Provides real-time data from centralized exchanges via their WebSocket APIs.

Supported CEXs:
- Binance: World's largest crypto exchange by volume
"""

from .binance import CEXStream as BinanceStream

__all__ = [
    "BinanceStream",
]
