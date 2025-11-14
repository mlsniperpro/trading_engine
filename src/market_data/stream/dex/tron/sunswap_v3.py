"""
SunSwap V3 stream for TRON.

SunSwap V3 is the dominant DEX on TRON:
- 78-89% of TRON DEX volume
- $288M TVL
- Concentrated liquidity (Uniswap V3 style)
- Smart Router contract: TCFNp179Lg46D16zKoumd4Poa2WFFdtqYj
"""

import logging
from typing import Optional, Dict
from decimal import Decimal

from .base import TronDEXStream

logger = logging.getLogger(__name__)


# SunSwap V3 contract addresses
SUNSWAP_V3_FACTORY = "TFU6bUTf6hFPT1bDWyg9bBcM3QZVZaZZcR"  # V3 Factory
SUNSWAP_V3_ROUTER = "TCFNp179Lg46D16zKoumd4Poa2WFFdtqYj"  # Smart Router (V3)

# Top SunSwap V3 pools (by TVL and volume)
SUNSWAP_V3_POOLS = {
    "USDT-USDC": {
        "address": "TBD",  # TODO: Get actual pool addresses from chain
        "token0": "USDT",
        "token1": "USDC",
        "fee": 100,  # 0.01%
    },
    "TRX-USDT": {
        "address": "TBD",
        "token0": "TRX",
        "token1": "USDT",
        "fee": 3000,  # 0.3%
    },
    "WTRX-USDT": {
        "address": "TBD",
        "token0": "WTRX",
        "token1": "USDT",
        "fee": 3000,
    },
}


class SunSwapV3Stream(TronDEXStream):
    """
    SunSwap V3 stream - TRON's #1 DEX.

    Monitors swap events on SunSwap V3 concentrated liquidity pools.
    Uses TronGrid API with efficient polling.

    Market Stats (2025):
    - 78-89% TRON DEX volume share
    - $288M Total Value Locked
    - $49-67M daily volume
    - Concentrated liquidity (Uniswap V3 fork)
    """

    def __init__(
        self,
        pools: Optional[list] = None,
        trongrid_api_key: Optional[str] = None,
        poll_interval: float = 2.0,
    ):
        """
        Initialize SunSwap V3 stream.

        Args:
            pools: List of pool addresses to monitor (default: all major pools)
            trongrid_api_key: Optional TronGrid API key
            poll_interval: Seconds between polls
        """
        # Use Smart Router as primary contract to monitor
        # This catches all V3 swaps routed through the router
        super().__init__(
            dex_name="sunswap_v3",
            contract_address=SUNSWAP_V3_ROUTER,
            event_name="Swap",
            trongrid_api_key=trongrid_api_key,
            poll_interval=poll_interval,
        )

        self.pools_to_monitor = pools or list(SUNSWAP_V3_POOLS.keys())
        logger.info(
            f"SunSwap V3 stream initialized - monitoring {len(self.pools_to_monitor)} pools "
            f"(78-89% TRON volume, $288M TVL)"
        )

    def _parse_swap_event(self, event: Dict) -> Optional[Dict]:
        """
        Parse SunSwap V3 swap event.

        V3 Swap event structure (Uniswap V3 compatible):
        - sender: address
        - recipient: address
        - amount0: int256 (token0 delta)
        - amount1: int256 (token1 delta)
        - sqrtPriceX96: uint160
        - liquidity: uint128
        - tick: int24

        Args:
            event: Raw TronGrid event

        Returns:
            Parsed swap data
        """
        try:
            result = event.get("result", {})

            # Extract swap parameters
            sender = result.get("sender", "")
            recipient = result.get("recipient", "")
            amount0 = result.get("amount0", 0)
            amount1 = result.get("amount1", 0)
            sqrt_price_x96 = result.get("sqrtPriceX96", 0)
            liquidity = result.get("liquidity", 0)
            tick = result.get("tick", 0)

            # Determine trade direction and amounts
            # In V3, negative amount means tokens out, positive means tokens in
            if amount0 < 0 and amount1 > 0:
                # Selling token0 for token1
                direction = "SELL_TOKEN0"
                amount_in = abs(amount0)
                amount_out = amount1
            elif amount0 > 0 and amount1 < 0:
                # Selling token1 for token0
                direction = "SELL_TOKEN1"
                amount_in = abs(amount1)
                amount_out = amount0
            else:
                direction = "UNKNOWN"
                amount_in = 0
                amount_out = 0

            # Calculate price (simplified - would need token decimals for accuracy)
            price = None
            if amount_in > 0 and amount_out > 0:
                price = float(amount_out) / float(amount_in)

            return {
                "pool": event.get("contract_address", "unknown"),
                "sender": sender,
                "recipient": recipient,
                "amount0": amount0,
                "amount1": amount1,
                "amount_in": amount_in,
                "amount_out": amount_out,
                "direction": direction,
                "price": price,
                "sqrt_price_x96": sqrt_price_x96,
                "liquidity": liquidity,
                "tick": tick,
                "transaction_id": event.get("transaction_id"),
                "block_number": event.get("block_number"),
                "block_timestamp": event.get("block_timestamp"),
                "dex": "sunswap_v3",
            }

        except Exception as e:
            logger.error(f"Error parsing SunSwap V3 swap event: {e}")
            return None


# Factory function for backward compatibility
def create_sunswap_v3_stream(**kwargs):
    """Create SunSwap V3 stream instance."""
    return SunSwapV3Stream(**kwargs)
