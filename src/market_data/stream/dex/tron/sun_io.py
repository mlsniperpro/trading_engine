"""
SUN.io stream for TRON.

SUN.io is the #4 TRON DEX by TVL:
- TVL: $2.62M
- Core protocol of the TRON DeFi ecosystem
- Acquired JustSwap in 2021 to create SunSwap
- Supports multiple token pairs
- Active trading and liquidity provision
"""

import logging
from typing import Optional, Dict
from decimal import Decimal

from .base import TronDEXStream

logger = logging.getLogger(__name__)


# SUN.io contract addresses
# Note: These need to be verified from official SUN.io documentation
SUN_IO_ROUTER = "TBD"  # TODO: Get actual SUN.io router address
SUN_IO_FACTORY = "TBD"  # TODO: Get actual SUN.io factory address

# Top SUN.io pairs
SUN_IO_PAIRS = {
    "SUN-TRX": {
        "address": "TBD",
        "token0": "SUN",
        "token1": "TRX",
    },
    "SUN-USDT": {
        "address": "TBD",
        "token0": "SUN",
        "token1": "USDT",
    },
}


class SunIOStream(TronDEXStream):
    """
    SUN.io stream - Core TRON DeFi protocol.

    Monitors swap events on SUN.io DEX.
    Uses TronGrid API with efficient polling.

    Market Stats (2025):
    - TVL: $2.62M (4th largest TRON DEX)
    - Core protocol of TRON DeFi ecosystem
    - Created SunSwap brand after acquiring JustSwap
    - Active community and development
    """

    def __init__(
        self,
        pairs: Optional[list] = None,
        trongrid_api_key: Optional[str] = None,
        poll_interval: float = 2.5,
    ):
        """
        Initialize SUN.io stream.

        Args:
            pairs: List of pair addresses to monitor (default: all pairs)
            trongrid_api_key: Optional TronGrid API key
            poll_interval: Seconds between polls
        """
        # Use router/factory as primary contract to monitor
        contract_address = SUN_IO_ROUTER if SUN_IO_ROUTER != "TBD" else "TBD"

        super().__init__(
            dex_name="sun_io",
            contract_address=contract_address,
            event_name="Swap",
            trongrid_api_key=trongrid_api_key,
            poll_interval=poll_interval,
        )

        self.pairs_to_monitor = pairs or list(SUN_IO_PAIRS.keys())

        if contract_address == "TBD":
            logger.warning(
                "SUN.io contract address not configured. "
                "Stream will not work until updated with actual address."
            )
        else:
            logger.info(
                f"SUN.io stream initialized - monitoring {len(self.pairs_to_monitor)} pairs "
                f"(TVL: $2.62M, TRON DeFi core protocol)"
            )

    def _parse_swap_event(self, event: Dict) -> Optional[Dict]:
        """
        Parse SUN.io swap event.

        SUN.io event structure (Uniswap V2 compatible):
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

            # Extract swap parameters (V2-style)
            sender = result.get("sender", "")
            to = result.get("to", "")
            amount0_in = int(result.get("amount0In", 0))
            amount1_in = int(result.get("amount1In", 0))
            amount0_out = int(result.get("amount0Out", 0))
            amount1_out = int(result.get("amount1Out", 0))

            # Determine trade direction
            if amount0_in > 0 and amount1_out > 0:
                direction = "TOKEN0_TO_TOKEN1"
                amount_in = amount0_in
                amount_out = amount1_out
            elif amount1_in > 0 and amount0_out > 0:
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
                "dex": "sun_io",
            }

        except Exception as e:
            logger.error(f"Error parsing SUN.io swap event: {e}")
            return None


# Factory function for backward compatibility
def create_sun_io_stream(**kwargs):
    """Create SUN.io stream instance."""
    return SunIOStream(**kwargs)
