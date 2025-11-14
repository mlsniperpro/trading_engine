"""
TRON DEX stream handlers using TronGrid API.

Provides real-time monitoring for top TRON DEXs with free TronGrid access:
- SunSwap V3: #1 TRON DEX (78-89% volume, $288M TVL, concentrated liquidity)
- SunSwap V2: Meme coin DEX ($431M TVL, Uniswap V2 style)
- SunSwap V1: Original TRON DEX ($452M TVL, highest TVL)
- JustMoney: Multi-chain DEX (taxed token support)

All streams use TronGrid REST API with efficient polling for reliable event monitoring.
NO WebSocket required - REST API is more stable for TRON.
"""

from .sunswap_v3 import SunSwapV3Stream
from .sunswap_v2 import SunSwapV2Stream
from .sunswap_v1 import SunSwapV1Stream
from .justmoney import JustMoneyStream

__all__ = [
    'SunSwapV3Stream',
    'SunSwapV2Stream',
    'SunSwapV1Stream',
    'JustMoneyStream',
]
