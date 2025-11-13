"""
DEX (Decentralized Exchange) stream handlers.

Provides real-time data from blockchain-based decentralized exchanges.

Ethereum DEXs (via Alchemy WebSocket):
- Uniswap V3: Market leader with concentrated liquidity
- Curve Finance: Stablecoin specialist with low slippage
- SushiSwap: Popular AMM (Uniswap V2 fork)
- Balancer V2: Multi-token weighted pools

Solana DEXs (via Solana RPC WebSocket):
- Pump.fun: #1 meme coin launchpad
- Raydium: Market leader (34% volume)
- Jupiter: DEX aggregator
- Orca: Whirlpools (concentrated liquidity)
- Meteora: DLMM (dynamic liquidity)
"""

# Ethereum DEXs
from .uniswap_v3 import DEXStream as UniswapV3Stream
from .curve import CurveStream
from .sushiswap import SushiSwapStream
from .balancer import BalancerStream

# Solana DEXs
from .solana import (
    PumpFunStream, RaydiumStream, JupiterStream,
    OrcaStream, MeteoraStream
)

__all__ = [
    # Ethereum
    "UniswapV3Stream",
    "CurveStream",
    "SushiSwapStream",
    "BalancerStream",
    # Solana
    "PumpFunStream",
    "RaydiumStream",
    "JupiterStream",
    "OrcaStream",
    "MeteoraStream",
]
