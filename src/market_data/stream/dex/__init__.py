"""
DEX (Decentralized Exchange) stream handlers.

Provides real-time data from blockchain-based decentralized exchanges via Alchemy WebSocket.

Supported DEXs:
- Uniswap V3: Market leader with concentrated liquidity
- Curve Finance: Stablecoin specialist with low slippage
- SushiSwap: Popular AMM (Uniswap V2 fork)
- Balancer V2: Multi-token weighted pools
"""

from .uniswap_v3 import DEXStream as UniswapV3Stream
from .curve import CurveStream
from .sushiswap import SushiSwapStream
from .balancer import BalancerStream

__all__ = [
    "UniswapV3Stream",
    "CurveStream",
    "SushiSwapStream",
    "BalancerStream",
]
