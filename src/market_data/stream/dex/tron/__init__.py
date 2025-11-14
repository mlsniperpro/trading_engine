"""
TRON DEX stream handlers using TronGrid API.

Provides real-time monitoring for top 4 TRON DEXs by TVL with free TronGrid access:
- SunSwap V1: $431M TVL (original TRON DEX, highest TVL)
- SunSwap V3: $288M TVL (#1 by volume 78-89%, concentrated liquidity)
- SunSwap V2: Meme coin DEX (Uniswap V2 style)
- SUN.io: $2.62M TVL (core TRON DeFi protocol, created SunSwap brand)

All streams use TronGrid REST API with efficient polling for reliable event monitoring.
NO WebSocket required - REST API is more stable for TRON.
"""

from .sunswap_v3 import SunSwapV3Stream
from .sunswap_v2 import SunSwapV2Stream
from .sunswap_v1 import SunSwapV1Stream
from .sun_io import SunIOStream

__all__ = [
    'SunSwapV3Stream',
    'SunSwapV2Stream',
    'SunSwapV1Stream',
    'SunIOStream',
]
