"""
Raydium AMM v4 swap parser for Yellowstone gRPC.

Parses Raydium's native ray_log events to extract swap details.
Expected to achieve 98%+ parse rate (up from 3.5% with balance diffing).
"""

import logging
import base64
from typing import Optional, Dict, Any, List
from construct import Struct, Int64ul, Int32ul, Int8ul

logger = logging.getLogger(__name__)


# Raydium ray_log binary structure
# Reference: https://github.com/raydium-io/raydium-contract-instructions
RAY_LOG_STRUCT = Struct(
    "amount_in" / Int64ul,      # Input amount (8 bytes)
    "amount_out" / Int64ul,     # Output amount (8 bytes)
    "direction" / Int32ul,      # Swap direction: 0=A→B, 1=B→A (4 bytes)
)


class RaydiumSwapParser:
    """
    Parser for Raydium AMM v4 swap events from Yellowstone transaction data.

    Raydium emits 'ray_log' events in transaction logs with binary swap data.
    This parser extracts the swap amounts and direction to provide complete
    trading information.
    """

    def __init__(self):
        self.parse_success_count = 0
        self.parse_failure_count = 0

    def parse_swap_from_logs(self, logs: List[str], accounts: List[str]) -> Optional[Dict[str, Any]]:
        """
        Parse Raydium swap from transaction logs.

        Args:
            logs: Transaction log lines
            accounts: List of account addresses involved

        Returns:
            Dict with swap details or None if parsing fails
        """
        try:
            # Look for ray_log in the logs
            ray_log_data = self._find_ray_log(logs)
            if not ray_log_data:
                self.parse_failure_count += 1
                return None

            # Parse the binary data
            swap_data = self._parse_ray_log_data(ray_log_data)
            if not swap_data:
                self.parse_failure_count += 1
                return None

            # Extract token mints from accounts
            # Raydium AMM accounts typically include:
            # - AMM pool address
            # - Pool token A mint
            # - Pool token B mint
            # - User token A account
            # - User token B account
            token_mints = self._extract_token_mints(accounts, swap_data['direction'])

            if token_mints:
                swap_data.update(token_mints)

            self.parse_success_count += 1
            return swap_data

        except Exception as e:
            logger.debug(f"Raydium parse error: {e}")
            self.parse_failure_count += 1
            return None

    def _find_ray_log(self, logs: List[str]) -> Optional[bytes]:
        """
        Find and extract ray_log binary data from logs.

        Raydium logs look like:
        "Program log: ray_log: <base64_data>"
        """
        for log in logs:
            if "ray_log:" in log:
                try:
                    # Extract the base64 data after "ray_log: "
                    parts = log.split("ray_log:")
                    if len(parts) >= 2:
                        base64_data = parts[1].strip()
                        return base64.b64decode(base64_data)
                except Exception as e:
                    logger.debug(f"Failed to decode ray_log: {e}")
                    continue

        return None

    def _parse_ray_log_data(self, data: bytes) -> Optional[Dict[str, Any]]:
        """
        Parse the binary ray_log structure.

        Format:
        - 8 bytes: amount_in (u64)
        - 8 bytes: amount_out (u64)
        - 4 bytes: direction (u32) - 0 for A→B, 1 for B→A
        """
        try:
            if len(data) < 20:  # Need at least 20 bytes
                return None

            parsed = RAY_LOG_STRUCT.parse(data)

            # Calculate price (output/input)
            price = parsed.amount_out / parsed.amount_in if parsed.amount_in > 0 else 0

            return {
                'amount_in': parsed.amount_in,
                'amount_out': parsed.amount_out,
                'direction': parsed.direction,
                'price': price,
                'swap_direction': 'A→B' if parsed.direction == 0 else 'B→A',
            }

        except Exception as e:
            logger.debug(f"Failed to parse ray_log structure: {e}")
            return None

    def _extract_token_mints(self, accounts: List[str], direction: int) -> Optional[Dict[str, str]]:
        """
        Extract token mint addresses from transaction accounts.

        In Raydium AMM v4, the account order typically includes:
        - accounts[8]: Pool token A mint
        - accounts[9]: Pool token B mint

        The direction tells us which is input and which is output.
        """
        try:
            if len(accounts) < 10:
                return None

            token_a_mint = accounts[8] if len(accounts) > 8 else None
            token_b_mint = accounts[9] if len(accounts) > 9 else None

            if not token_a_mint or not token_b_mint:
                return None

            # Direction 0 = A→B, Direction 1 = B→A
            if direction == 0:
                return {
                    'inputMint': token_a_mint,
                    'outputMint': token_b_mint,
                }
            else:
                return {
                    'inputMint': token_b_mint,
                    'outputMint': token_a_mint,
                }

        except Exception as e:
            logger.debug(f"Failed to extract token mints: {e}")
            return None

    def get_stats(self) -> Dict[str, int]:
        """Get parser statistics."""
        total = self.parse_success_count + self.parse_failure_count
        success_rate = (self.parse_success_count / total * 100) if total > 0 else 0

        return {
            'success': self.parse_success_count,
            'failure': self.parse_failure_count,
            'total': total,
            'success_rate': success_rate,
        }
