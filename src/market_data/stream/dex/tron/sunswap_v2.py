"""
SunSwap V2 stream for TRON.

SunSwap V2 is a Uniswap V2 style AMM:
- $431M TVL
- Popular for meme coins and new tokens
- Constant product formula (x * y = k)
- Router: TKzxdSv2FZKQrEqkKVgp5DcwEXBEKMg2Ax
"""

import logging
from typing import Optional, Dict
from decimal import Decimal

from .base import TronDEXStream

logger = logging.getLogger(__name__)


# SunSwap V2 contract addresses
SUNSWAP_V2_FACTORY = "TKWJdrQkqHisa1X8HUdHEfREvTzw4pMAaY"  # V2 Factory
SUNSWAP_V2_ROUTER = "TKzxdSv2FZKQrEqkKVgp5DcwEXBEKMg2Ax"  # V2 Router

# Top SunSwap V2 pairs (by volume)
SUNSWAP_V2_PAIRS = {
    "TRX-USDT": {
        "address": "TBD",  # TODO: Get actual pair addresses
        "token0": "TRX",
        "token1": "USDT",
    },
    "WTRX-USDT": {
        "address": "TBD",
        "token0": "WTRX",
        "token1": "USDT",
    },
    "SUN-TRX": {
        "address": "TBD",
        "token0": "SUN",
        "token1": "TRX",
    },
}


class SunSwapV2Stream(TronDEXStream):
    """
    SunSwap V2 stream - TRON's Uniswap V2 style DEX.

    Monitors swap events on SunSwap V2 AMM pairs.
    Uses TronGrid API with efficient polling.

    Market Stats (2025):
    - $431M Total Value Locked
    - Uniswap V2 fork (constant product AMM)
    - Popular for meme coins and new token launches
    - Legacy pairs still have significant volume
    """

    def __init__(
        self,
        pairs: Optional[list] = None,
        trongrid_api_key: Optional[str] = None,
        poll_interval: float = 2.0,
    ):
        """
        Initialize SunSwap V2 stream.

        Args:
            pairs: List of pair addresses to monitor (default: all major pairs)
            trongrid_api_key: Optional TronGrid API key
            poll_interval: Seconds between polls
        """
        # Use V2 Router as primary contract to monitor
        super().__init__(
            dex_name="sunswap_v2",
            contract_address=SUNSWAP_V2_ROUTER,
            event_name="Swap",
            trongrid_api_key=trongrid_api_key,
            poll_interval=poll_interval,
        )

        self.pairs_to_monitor = pairs or list(SUNSWAP_V2_PAIRS.keys())
        logger.info(
            f"SunSwap V2 stream initialized - monitoring {len(self.pairs_to_monitor)} pairs "
            f"($431M TVL, meme coin DEX)"
        )

    def _parse_swap_event(self, event: Dict) -> Optional[Dict]:
        """
        Parse SunSwap V2 swap event.

        V2 Swap event structure (Uniswap V2 compatible):
        - sender: address
        - amount0In: uint256
        - amount1In: uint256
        - amount0Out: uint256
        - amount1Out: uint256
        - to: address (recipient)

        Args:
            event: Raw TronGrid event

        Returns:
            Parsed swap data
        """
        try:
            result = event.get("result", {})

            # Extract swap parameters
            sender = result.get("sender", "")
            to = result.get("to", "")
            amount0_in = int(result.get("amount0In", 0))
            amount1_in = int(result.get("amount1In", 0))
            amount0_out = int(result.get("amount0Out", 0))
            amount1_out = int(result.get("amount1Out", 0))

            # Determine trade direction
            if amount0_in > 0 and amount1_out > 0:
                # Swapping token0 -> token1
                direction = "TOKEN0_TO_TOKEN1"
                amount_in = amount0_in
                amount_out = amount1_out
            elif amount1_in > 0 and amount0_out > 0:
                # Swapping token1 -> token0
                direction = "TOKEN1_TO_TOKEN0"
                amount_in = amount1_in
                amount_out = amount0_out
            else:
                direction = "UNKNOWN"
                amount_in = 0
                amount_out = 0

            # Calculate price
            price = None
            if amount_in > 0 and amount_out > 0:
                price = float(amount_out) / float(amount_in)

            return {
                "pair": event.get("contract_address", "unknown"),
                "sender": sender,
                "recipient": to,
                "amount0_in": amount0_in,
                "amount1_in": amount1_in,
                "amount0_out": amount0_out,
                "amount1_out": amount1_out,
                "amount_in": amount_in,
                "amount_out": amount_out,
                "direction": direction,
                "price": price,
                "transaction_id": event.get("transaction_id"),
                "block_number": event.get("block_number"),
                "block_timestamp": event.get("block_timestamp"),
                "dex": "sunswap_v2",
            }

        except Exception as e:
            logger.error(f"Error parsing SunSwap V2 swap event: {e}")
            return None


# Factory function for backward compatibility
def create_sunswap_v2_stream(**kwargs):
    """Create SunSwap V2 stream instance."""
    return SunSwapV2Stream(**kwargs)
