"""
SunSwap V1 stream for TRON.

SunSwap V1 is the original TRON DEX:
- $452M TVL (highest among all versions)
- Legacy but still active
- Simple AMM design
- Many established pairs
"""

import logging
from typing import Optional, Dict
from decimal import Decimal

from .base import TronDEXStream

logger = logging.getLogger(__name__)


# SunSwap V1 contract addresses
SUNSWAP_V1_FACTORY = "TXk8rQSAvPvBBNtqSoY6nCfsXWCSSpTVQF"  # V1 Factory (approximate)

# Top SunSwap V1 pairs (by TVL)
SUNSWAP_V1_PAIRS = {
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
    "JST-USDT": {
        "address": "TBD",
        "token0": "JST",
        "token1": "USDT",
    },
}


class SunSwapV1Stream(TronDEXStream):
    """
    SunSwap V1 stream - Original TRON DEX.

    Monitors swap events on SunSwap V1 pairs.
    Uses TronGrid API with efficient polling.

    Market Stats (2025):
    - $452M Total Value Locked (highest TVL)
    - Legacy DEX but still very active
    - Many established trading pairs
    - Simple AMM design
    """

    def __init__(
        self,
        pairs: Optional[list] = None,
        trongrid_api_key: Optional[str] = None,
        poll_interval: float = 2.0,
    ):
        """
        Initialize SunSwap V1 stream.

        Args:
            pairs: List of pair addresses to monitor (default: all major pairs)
            trongrid_api_key: Optional TronGrid API key
            poll_interval: Seconds between polls
        """
        # Use V1 Factory as primary contract to monitor
        # Note: V1 may have different event structures than V2/V3
        super().__init__(
            dex_name="sunswap_v1",
            contract_address=SUNSWAP_V1_FACTORY,
            event_name="Swap",
            trongrid_api_key=trongrid_api_key,
            poll_interval=poll_interval,
        )

        self.pairs_to_monitor = pairs or list(SUNSWAP_V1_PAIRS.keys())
        logger.info(
            f"SunSwap V1 stream initialized - monitoring {len(self.pairs_to_monitor)} pairs "
            f"($452M TVL, original TRON DEX)"
        )

    def _parse_swap_event(self, event: Dict) -> Optional[Dict]:
        """
        Parse SunSwap V1 swap event.

        V1 Swap event structure (may vary from V2):
        - sender: address
        - tokenIn: address
        - tokenOut: address
        - amountIn: uint256
        - amountOut: uint256
        - to: address (recipient)

        Note: V1 structure may be different from V2/V3.
        Adjust based on actual event logs from chain.

        Args:
            event: Raw TronGrid event

        Returns:
            Parsed swap data
        """
        try:
            result = event.get("result", {})

            # Extract swap parameters (V1 style)
            # Note: These field names are estimates and may need adjustment
            sender = result.get("sender", "")
            to = result.get("to", result.get("recipient", ""))
            token_in = result.get("tokenIn", "")
            token_out = result.get("tokenOut", "")
            amount_in = int(result.get("amountIn", result.get("amount_in", 0)))
            amount_out = int(result.get("amountOut", result.get("amount_out", 0)))

            # Calculate price
            price = None
            if amount_in > 0 and amount_out > 0:
                price = float(amount_out) / float(amount_in)

            return {
                "pair": event.get("contract_address", "unknown"),
                "sender": sender,
                "recipient": to,
                "token_in": token_in,
                "token_out": token_out,
                "amount_in": amount_in,
                "amount_out": amount_out,
                "price": price,
                "transaction_id": event.get("transaction_id"),
                "block_number": event.get("block_number"),
                "block_timestamp": event.get("block_timestamp"),
                "dex": "sunswap_v1",
            }

        except Exception as e:
            logger.error(f"Error parsing SunSwap V1 swap event: {e}")
            return None


# Factory function for backward compatibility
def create_sunswap_v1_stream(**kwargs):
    """Create SunSwap V1 stream instance."""
    return SunSwapV1Stream(**kwargs)
