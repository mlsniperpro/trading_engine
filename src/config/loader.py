"""
Configuration loader.

Loads and caches configuration files from the config/ directory.
"""

import yaml
from pathlib import Path
from typing import Dict, Any
from functools import lru_cache

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent


@lru_cache(maxsize=32)
def load_config(config_name: str) -> Dict[str, Any]:
    """
    Load a configuration file from config/ directory.

    Args:
        config_name: Name of the config file (without .yaml extension)

    Returns:
        Dictionary containing configuration data

    Example:
        >>> dex_config = load_config('dex')
        >>> pools = dex_config['uniswap_v3']['pools']
    """
    config_path = PROJECT_ROOT / 'config' / f'{config_name}.yaml'

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


# ============================================================================
# DEX Configuration Loaders
# ============================================================================

def get_dex_config() -> Dict[str, Any]:
    """
    Get complete DEX configuration for all supported DEXs.

    Returns:
        Dictionary with all DEX configurations (Uniswap, Curve, SushiSwap, Balancer)
    """
    return load_config('dex')


def get_uniswap_config() -> Dict[str, Any]:
    """
    Get Uniswap V3 configuration.

    Returns:
        Dictionary with pools, routers, and ABI configurations
    """
    dex_config = get_dex_config()
    return dex_config['uniswap_v3']


def get_curve_config() -> Dict[str, Any]:
    """
    Get Curve Finance configuration.

    Returns:
        Dictionary with Curve pools and router
    """
    dex_config = get_dex_config()
    return dex_config['curve']


def get_sushiswap_config() -> Dict[str, Any]:
    """
    Get SushiSwap configuration.

    Returns:
        Dictionary with SushiSwap pairs and router
    """
    dex_config = get_dex_config()
    return dex_config['sushiswap']


def get_balancer_config() -> Dict[str, Any]:
    """
    Get Balancer V2 configuration.

    Returns:
        Dictionary with Balancer pools and vault
    """
    dex_config = get_dex_config()
    return dex_config['balancer']


# ============================================================================
# Uniswap-specific Helpers (backward compatibility)
# ============================================================================

def get_pool_config(pool_name: str) -> Dict[str, Any]:
    """
    Get configuration for a specific Uniswap pool.

    Args:
        pool_name: Pool identifier (e.g., 'ETH-USDC-0.3%')

    Returns:
        Pool configuration dictionary

    Raises:
        KeyError: If pool not found in configuration
    """
    config = get_uniswap_config()
    return config['pools'][pool_name]


def get_all_pool_addresses() -> Dict[str, str]:
    """
    Get all Uniswap pool addresses from configuration.

    Returns:
        Dictionary mapping pool names to addresses
    """
    config = get_uniswap_config()
    return {
        name: pool['address']
        for name, pool in config['pools'].items()
    }


def get_pool_abi() -> list:
    """
    Get Uniswap V3 pool ABI from configuration.

    Returns:
        List of ABI definitions for pool contract
    """
    config = get_uniswap_config()
    return config['pool_abi']


# ============================================================================
# Token Configuration
# ============================================================================

def get_token_addresses() -> Dict[str, str]:
    """
    Get all token addresses from DEX configuration.

    Returns:
        Dictionary mapping token symbols to addresses
    """
    dex_config = get_dex_config()
    return dex_config.get('tokens', {})


def get_token_address(symbol: str) -> str:
    """
    Get address for a specific token.

    Args:
        symbol: Token symbol (e.g., 'WETH', 'USDC')

    Returns:
        Token contract address

    Raises:
        KeyError: If token not found
    """
    tokens = get_token_addresses()
    return tokens[symbol]


# ============================================================================
# Arbitrage Configuration
# ============================================================================

def get_arbitrage_config() -> Dict[str, Any]:
    """
    Get arbitrage monitoring configuration.

    Returns:
        Dictionary with arbitrage settings (threshold, gas limits, etc.)
    """
    dex_config = get_dex_config()
    return dex_config.get('arbitrage', {})
