"""
Market data streaming layer.

This module provides real-time market data from various sources organized by platform type:

- dex/: Decentralized exchanges (Uniswap V3, Curve, SushiSwap, Balancer)
- cex/: Centralized exchanges (Binance)
- forex/: Foreign exchange markets (coming soon)
"""

# Import all DEX streams
from .dex import UniswapV3Stream, CurveStream, SushiSwapStream, BalancerStream

# Import all CEX streams
from .cex import BinanceStream

# Import manager
from .manager import MarketDataManager

__all__ = [
    # DEX streams
    "UniswapV3Stream",
    "CurveStream",
    "SushiSwapStream",
    "BalancerStream",
    # CEX streams
    "BinanceStream",
    # Manager
    "MarketDataManager",
]
