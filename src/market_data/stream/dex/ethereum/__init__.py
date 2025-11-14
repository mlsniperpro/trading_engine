"""
Ethereum DEX stream handlers.

Provides real-time monitoring for major Ethereum decentralized exchanges:
- Uniswap V3: Concentrated liquidity AMM (#1 DEX by volume)
- Curve Finance: Stablecoin-focused AMM
- SushiSwap: Community-driven AMM (Uniswap V2 fork)
- Balancer V2: Multi-token weighted pools

All streams use Ethereum JSON-RPC for event monitoring.
"""

from .uniswap_v3 import DEXStream as UniswapV3Stream
from .curve import CurveStream
from .sushiswap import SushiSwapStream
from .balancer import BalancerStream

__all__ = [
    'UniswapV3Stream',
    'CurveStream',
    'SushiSwapStream',
    'BalancerStream',
]
