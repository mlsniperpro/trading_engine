"""
Generic Yellowstone gRPC-based DEX stream for Solana.

This replaces the old Helius WebSocket approach with FREE unlimited Yellowstone gRPC.
Works for ALL Solana DEXs: Jupiter, Raydium, Orca, Meteora, Pump.fun
"""

import asyncio
import logging
from typing import Callable, Optional, List
from datetime import datetime

from .client import YellowstoneClient, SwapData


logger = logging.getLogger(__name__)


class YellowstoneDEXStream:
    """
    Generic Yellowstone gRPC stream for any Solana DEX.

    Benefits over old Helius WebSocket approach:
    - ✅ FREE unlimited access
    - ✅ FULL transaction data with parsed swap details
    - ✅ NO rate limits
    - ✅ NO API keys
    - ✅ Lower latency with gRPC
    - ✅ More reliable connection
    """

    def __init__(
        self,
        dex_name: str,
        program_id: str,
        geyser_endpoint: str = "solana-yellowstone-grpc.publicnode.com:443",
        commitment: str = "confirmed",
    ):
        """
        Initialize Yellowstone DEX stream.

        Args:
            dex_name: Name of the DEX (e.g., "jupiter", "raydium", "orca")
            program_id: Solana program ID for the DEX
            geyser_endpoint: Yellowstone gRPC endpoint (default: PublicNode FREE)
            commitment: Commitment level (processed, confirmed, finalized)
        """
        self.dex_name = dex_name
        self.program_id = program_id
        self.geyser_endpoint = geyser_endpoint
        self.commitment = commitment

        # Yellowstone client (with program_id for parser selection)
        self.client = YellowstoneClient(endpoint=geyser_endpoint, program_id=program_id)

        # Callbacks
        self._swap_callbacks: List[Callable] = []
        self._error_callbacks: List[Callable] = []

        # Stats
        self._swap_count = 0
        self._parsed_count = 0
        self._error_count = 0
        self._start_time: Optional[datetime] = None
        self._reconnect_count = 0

        # Reconnect settings
        self._should_stop = False
        self._max_reconnect_delay = 60  # Max 60 seconds between reconnects
        self._initial_reconnect_delay = 1  # Start with 1 second

        logger.info(
            f"🟣 Initialized {dex_name.upper()} Yellowstone stream "
            f"(program: {program_id[:8]}...)"
        )

    def on_swap(self, callback: Callable):
        """Register callback for swap events."""
        self._swap_callbacks.append(callback)

    def on_error(self, callback: Callable):
        """Register callback for error events."""
        self._error_callbacks.append(callback)

    def on_launch(self, callback: Callable):
        """Register callback for launch events (Pump.fun compatibility)."""
        # For Pump.fun, we treat swaps as potential launches
        # This is for backward compatibility with the manager
        pass

    def on_trade(self, callback: Callable):
        """Register callback for trade events (Pump.fun compatibility)."""
        # Alias for on_swap - for backward compatibility
        self.on_swap(callback)

    def on_graduate(self, callback: Callable):
        """Register callback for graduate events (Pump.fun compatibility)."""
        # For Pump.fun graduation events - not applicable to Yellowstone generic stream
        # This is for backward compatibility with the manager
        pass

    async def stop(self):
        """Stop the stream gracefully."""
        self._should_stop = True
        try:
            if self.client:
                await self.client.close()
        except Exception as e:
            logger.error(f"Error stopping {self.dex_name} stream: {e}")

    async def start(self):
        """
        Start monitoring DEX swaps via Yellowstone gRPC with auto-reconnect.

        Connects to PublicNode's FREE Yellowstone gRPC and streams all
        transactions for this DEX in real-time with FULL parsed data.

        Automatically reconnects on connection failures with exponential backoff.
        """
        logger.info(f"🚀 Starting {self.dex_name.upper()} Yellowstone stream...")
        self._start_time = datetime.now()

        reconnect_delay = self._initial_reconnect_delay

        while not self._should_stop:
            try:
                # Recreate client if needed (after disconnect)
                if self._reconnect_count > 0:
                    self.client = YellowstoneClient(
                        endpoint=self.geyser_endpoint,
                        program_id=self.program_id
                    )

                # Connect to Yellowstone gRPC
                await self.client.connect()

                # Test connection
                pong = await self.client.ping()
                logger.info(f"✅ Geyser connection verified: {pong}")

                # Reset reconnect delay on successful connection
                if self._reconnect_count > 0:
                    logger.info(
                        f"🔄 {self.dex_name.upper()} reconnected successfully "
                        f"(reconnect #{self._reconnect_count})"
                    )
                reconnect_delay = self._initial_reconnect_delay

                logger.info(
                    f"📡 Subscribing to {self.dex_name.upper()} program: {self.program_id} "
                    f"({self.commitment})"
                )

                # Subscribe to transactions
                async for swap_data in self.client.subscribe_to_program(
                    program_ids=[self.program_id],
                    commitment=self.commitment,
                ):
                    await self._handle_swap(swap_data)

            except KeyboardInterrupt:
                logger.info(f"⏹️  Stopping {self.dex_name.upper()} Yellowstone stream...")
                self._should_stop = True
                break

            except Exception as e:
                logger.error(f"❌ {self.dex_name.upper()} Yellowstone stream error: {e}")
                self._error_count += 1

                # Fire error callbacks
                for callback in self._error_callbacks:
                    try:
                        callback({"error": str(e), "dex": self.dex_name})
                    except Exception as cb_error:
                        logger.error(f"Error callback failed: {cb_error}")

                # Close current connection
                try:
                    await self.client.close()
                except Exception:
                    pass

                # Don't reconnect if stopping
                if self._should_stop:
                    break

                # Auto-reconnect with exponential backoff
                self._reconnect_count += 1
                logger.info(
                    f"🔄 {self.dex_name.upper()} will reconnect in {reconnect_delay}s "
                    f"(attempt #{self._reconnect_count})"
                )
                await asyncio.sleep(reconnect_delay)

                # Exponential backoff: 1s -> 2s -> 4s -> 8s -> ... -> max 60s
                reconnect_delay = min(reconnect_delay * 2, self._max_reconnect_delay)

        # Final cleanup
        try:
            await self.client.close()
        except Exception:
            pass

        self._log_stats()

    async def _handle_swap(self, swap_data: SwapData):
        """Process swap data from Yellowstone stream."""
        try:
            self._swap_count += 1

            # Track if we have parsed details
            if swap_data.swap_details:
                self._parsed_count += 1

            # Create event data
            event_data = {
                "signature": swap_data.signature,
                "slot": swap_data.slot,
                "block_time": swap_data.block_time,
                "success": swap_data.success,
                "error": swap_data.error,
                "accounts": swap_data.accounts,
                "programs": swap_data.programs,
                "logs": swap_data.logs,
                "raw_transaction": swap_data.raw_transaction,
                "swap_details": swap_data.swap_details,
                "dex": self.dex_name,
                "program_id": self.program_id,
            }

            # Log swap
            parsed_status = "✅ Parsed" if swap_data.swap_details else "📝 Detected"
            logger.info(
                f"🔄 {self.dex_name.upper()} Swap #{self._swap_count} | "
                f"{parsed_status} | "
                f"Sig: {swap_data.signature[:16]}... | "
                f"Slot: {swap_data.slot}"
            )

            # Fire callbacks
            for callback in self._swap_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event_data)
                    else:
                        callback(event_data)
                except Exception as e:
                    logger.error(f"Swap callback error: {e}")

        except Exception as e:
            logger.error(f"Error handling swap: {e}")
            self._error_count += 1

    def _log_stats(self):
        """Log final statistics."""
        if self._start_time:
            duration = (datetime.now() - self._start_time).total_seconds()
            logger.info(
                f"📊 {self.dex_name.upper()} Yellowstone Stats: "
                f"{self._swap_count} swaps "
                f"({self._parsed_count} parsed), "
                f"{self._error_count} errors, "
                f"{self._reconnect_count} reconnects, "
                f"{duration:.1f}s runtime"
            )
