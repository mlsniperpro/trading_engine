"""
Jupiter swap event parser for Yellowstone gRPC transactions.

Parses Jupiter v6 swap events to extract:
- Input/output token mints
- Input/output amounts
- AMM used
"""

import base58
import logging
from typing import Optional, Dict, Any
from construct import Int64ul, Bytes, Struct as cStruct

logger = logging.getLogger(__name__)

# Public key is 32 bytes
PUBLIC_KEY_LAYOUT = Bytes(32)

# Jupiter Swap Event structure
JUP_SWAP_EVENT = cStruct(
    "amm" / PUBLIC_KEY_LAYOUT,
    "inputMint" / PUBLIC_KEY_LAYOUT,
    "inputAmount" / Int64ul,
    "outputMint" / PUBLIC_KEY_LAYOUT,
    "outputAmount" / Int64ul,
)

# Jupiter v6 discriminators
FIRST_DISCRIMINATOR = 2133240923048723940  # [228, 69, 165, 46, 81, 203, 154, 29]
SECOND_DISCRIMINATOR = 16316831888147596864  # [64, 198, 205, 232, 38, 8, 113, 226]


class JupiterSwapParser:
    """
    Parser for Jupiter v6 swap events from transaction logs.

    Extracts actionable trading data:
    - Token addresses (input/output mints)
    - Token amounts (input/output)
    - AMM used for the swap
    - Calculated price
    """

    def parse_swap_from_logs(self, logs: list[str], accounts: list[str] = None) -> Optional[Dict[str, Any]]:
        """
        Parse Jupiter swap event from transaction logs.

        Jupiter emits swap events as "Program data:" log entries.

        Args:
            logs: List of transaction log messages
            accounts: List of account addresses (optional, for compatibility)

        Returns:
            Dict with swap details or None if not found
        """
        try:
            # Find "Program data:" logs (contains base64-encoded event data)
            for log in logs:
                if "Program data:" in log:
                    # Extract the base64 data after "Program data: "
                    data_str = log.split("Program data: ")[1].strip()

                    # Decode from base64
                    import base64
                    try:
                        event_data = base64.b64decode(data_str)
                    except Exception:
                        continue

                    # Try to parse as Jupiter swap event
                    swap_data = self._parse_event_data(event_data)
                    if swap_data:
                        return swap_data

            return None

        except Exception as e:
            logger.error(f"Error parsing Jupiter swap from logs: {e}")
            return None

    def _parse_event_data(self, event_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Parse Jupiter swap event data.

        Format:
        - 8 bytes: discriminator (varies)
        - 32 bytes: amm public key
        - 32 bytes: input mint
        - 8 bytes: input amount (u64 little-endian)
        - 32 bytes: output mint
        - 8 bytes: output amount (u64 little-endian)

        Args:
            event_data: Raw event bytes

        Returns:
            Parsed swap data or None
        """
        try:
            # Need at least 8 bytes for discriminator
            if len(event_data) < 8:
                return None

            # Skip discriminator (8 bytes) and try to parse
            bytes_event = event_data[8:]

            # Need 32 + 32 + 8 + 32 + 8 = 112 bytes for swap event
            if len(bytes_event) < 112:
                return None

            try:
                decoded = JUP_SWAP_EVENT.parse(bytes_event)
            except Exception:
                # Try with 16-byte offset (two discriminators)
                if len(event_data) < 16:
                    return None
                bytes_event = event_data[16:]
                if len(bytes_event) < 112:
                    return None
                decoded = JUP_SWAP_EVENT.parse(bytes_event)

            # Convert to readable format
            input_mint = base58.b58encode(bytes(decoded.inputMint)).decode()
            output_mint = base58.b58encode(bytes(decoded.outputMint)).decode()
            amm = base58.b58encode(bytes(decoded.amm)).decode()

            input_amount = decoded.inputAmount
            output_amount = decoded.outputAmount

            # Sanity check - amounts should be reasonable
            if input_amount == 0 or output_amount == 0:
                return None

            # Calculate price (output per input)
            price = output_amount / input_amount if input_amount > 0 else 0

            result = {
                'amm': amm,
                'inputMint': input_mint,
                'inputAmount': input_amount,
                'outputMint': output_mint,
                'outputAmount': output_amount,
                'price': price,
            }

            logger.debug(f"Parsed Jupiter swap: {input_amount} {input_mint[:8]}... -> {output_amount} {output_mint[:8]}...")

            return result

        except Exception as e:
            logger.debug(f"Failed to parse event data: {e}")
            return None


# Singleton instance
_parser = None

def get_jupiter_parser() -> JupiterSwapParser:
    """Get shared Jupiter swap parser instance."""
    global _parser
    if _parser is None:
        _parser = JupiterSwapParser()
    return _parser
