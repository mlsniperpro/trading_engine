"""
Market data streaming layer.

This module provides real-time market data from various sources:
- DEX: Decentralized exchanges (Uniswap, etc.) via blockchain WebSocket
- CEX: Centralized exchanges (Binance, Bybit) via exchange WebSocket APIs
"""

from .dex_stream import DEXStream
from .cex_stream import CEXStream
from .manager import MarketDataManager

__all__ = [
    "DEXStream",
    "CEXStream",
    "MarketDataManager",
]
