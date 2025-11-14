"""
Solana DEX stream handlers using Yellowstone gRPC.

Provides real-time monitoring for top Solana DEXs with FREE unlimited access:
- Jupiter: DEX aggregator (highest overall volume)
- Raydium: #1 volume DEX (34%)
- Orca: Whirlpools (concentrated liquidity, 19%)
- Meteora: DLMM (dynamic liquidity, 22%)
- Pump.fun: Meme coin launchpad

All streams use PublicNode's FREE Yellowstone gRPC for full swap data parsing.
NO rate limits, NO API keys, NO costs!
"""

import yaml

# Load config
def _load_config():
    config_path = "/workspaces/trading_engine/config/solana_dex.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

_CONFIG = _load_config()

# Import generic Yellowstone stream
from .yellowstone import YellowstoneDEXStream

# Factory functions for each DEX
def JupiterStream(**kwargs):
    """Create Jupiter Yellowstone stream."""
    # Filter out unsupported kwargs
    supported = {'geyser_endpoint', 'commitment'}
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in supported}

    return YellowstoneDEXStream(
        dex_name="jupiter",
        program_id=_CONFIG['jupiter']['program_id'],
        **filtered_kwargs
    )

def RaydiumStream(**kwargs):
    """Create Raydium Yellowstone stream."""
    # Filter out unsupported kwargs
    supported = {'geyser_endpoint', 'commitment'}
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in supported}

    return YellowstoneDEXStream(
        dex_name="raydium",
        program_id=_CONFIG['raydium']['program_id'],
        **filtered_kwargs
    )

def OrcaStream(**kwargs):
    """Create Orca Yellowstone stream."""
    # Filter out unsupported kwargs
    supported = {'geyser_endpoint', 'commitment'}
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in supported}

    return YellowstoneDEXStream(
        dex_name="orca",
        program_id=_CONFIG['orca']['program_id'],
        **filtered_kwargs
    )

def MeteoraStream(**kwargs):
    """Create Meteora Yellowstone stream."""
    # Filter out unsupported kwargs
    supported = {'geyser_endpoint', 'commitment'}
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in supported}

    return YellowstoneDEXStream(
        dex_name="meteora",
        program_id=_CONFIG['meteora']['program_id'],
        **filtered_kwargs
    )

def PumpFunStream(**kwargs):
    """Create Pump.fun Yellowstone stream."""
    # Filter out unsupported kwargs (like min_market_cap_usd)
    supported = {'geyser_endpoint', 'commitment'}
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in supported}

    return YellowstoneDEXStream(
        dex_name="pumpfun",
        program_id=_CONFIG['pump_fun']['program_id'],
        **filtered_kwargs
    )

# Legacy compatibility - keep old RaydiumGeyserStream name
RaydiumGeyserStream = RaydiumStream

__all__ = [
    'JupiterStream',
    'RaydiumStream',
    'OrcaStream',
    'MeteoraStream',
    'PumpFunStream',
    'RaydiumGeyserStream',  # Legacy name
]
