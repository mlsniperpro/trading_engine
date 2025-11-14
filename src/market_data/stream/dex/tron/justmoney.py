"""
JustMoney stream for TRON.

JustMoney is a smaller but growing TRON DEX:
- Multi-chain swap support
- First DEX with full taxed token support on TRON
- Lower volume but active community
- Recent 24h volume: ~$3.5K (growing)
"""

import logging
from typing import Optional, Dict
from decimal import Decimal

from .base import TronDEXStream

logger = logging.getLogger(__name__)


# JustMoney contract addresses
# Note: These are estimates based on available data
# Actual addresses should be verified from JustMoney official docs
JUSTMONEY_ROUTER = "TBD"  # TODO: Get actual JustMoney router address
JUSTMONEY_FACTORY = "TBD"  # TODO: Get actual JustMoney factory address

# Top JustMoney pairs
JUSTMONEY_PAIRS = {
    "TRX-USDT": {
        "address": "TBD",
        "token0": "TRX",
        "token1": "USDT",
    },
    "WTRX-USDT": {
        "address": "TBD",
        "token0": "WTRX",
        "token1": "USDT",
    },
}


class JustMoneyStream(TronDEXStream):
    """
    JustMoney stream - Multi-chain TRON DEX.

    Monitors swap events on JustMoney DEX.
    Uses TronGrid API with efficient polling.

    Market Stats (2025):
    - First multi-chain swap on TRON
    - Full support for taxed tokens
    - Growing community DEX
    - Lower volume but increasing adoption
    """

    def __init__(
        self,
        pairs: Optional[list] = None,
        trongrid_api_key: Optional[str] = None,
        poll_interval: float = 3.0,  # Slightly longer interval for lower volume DEX
    ):
        """
        Initialize JustMoney stream.

        Args:
            pairs: List of pair addresses to monitor (default: all pairs)
            trongrid_api_key: Optional TronGrid API key
            poll_interval: Seconds between polls
        """
        # Use router/factory as primary contract to monitor
        # If we don't have the actual address, this will need to be updated
        contract_address = JUSTMONEY_ROUTER if JUSTMONEY_ROUTER != "TBD" else "TBD"

        super().__init__(
            dex_name="justmoney",
            contract_address=contract_address,
            event_name="Swap",
            trongrid_api_key=trongrid_api_key,
            poll_interval=poll_interval,
        )

        self.pairs_to_monitor = pairs or list(JUSTMONEY_PAIRS.keys())

        if contract_address == "TBD":
            logger.warning(
                "JustMoney contract address not configured. "
                "Stream will not work until updated with actual address."
            )
        else:
            logger.info(
                f"JustMoney stream initialized - monitoring {len(self.pairs_to_monitor)} pairs "
                f"(multi-chain DEX, taxed token support)"
            )

    def _parse_swap_event(self, event: Dict) -> Optional[Dict]:
        """
        Parse JustMoney swap event.

        JustMoney event structure (likely Uniswap V2 compatible):
        - sender: address
        - amount0In: uint256
        - amount1In: uint256
        - amount0Out: uint256
        - amount1Out: uint256
        - to: address (recipient)

        May have additional fields for taxed token handling.

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
                "dex": "justmoney",
            }

        except Exception as e:
            logger.error(f"Error parsing JustMoney swap event: {e}")
            return None


# Factory function for backward compatibility
def create_justmoney_stream(**kwargs):
    """Create JustMoney stream instance."""
    return JustMoneyStream(**kwargs)
