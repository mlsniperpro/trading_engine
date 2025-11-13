"""
Market data streaming layer.

This module provides real-time market data from various sources:
- DEX: Decentralized exchanges (Uniswap V3, Curve, SushiSwap, Balancer) via blockchain WebSocket
- CEX: Centralized exchanges (Binance, Bybit) via exchange WebSocket APIs
"""

from .dex_stream import DEXStream
from .cex_stream import CEXStream
from .curve_stream import CurveStream
from .sushiswap_stream import SushiSwapStream
from .balancer_stream import BalancerStream
from .manager import MarketDataManager

__all__ = [
    "DEXStream",
    "CEXStream",
    "CurveStream",
    "SushiSwapStream",
    "BalancerStream",
    "MarketDataManager",
]
