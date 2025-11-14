"""
Base TRON DEX stream using TronGrid API.

Uses HTTP polling with async/await to monitor smart contract events.
Since TRON doesn't have stable WebSocket endpoints, we use TronGrid REST API
with efficient polling to monitor swap events.
"""

import asyncio
import logging
from typing import Callable, Optional, List, Dict
from datetime import datetime
import aiohttp
from decimal import Decimal

logger = logging.getLogger(__name__)


class TronDEXStream:
    """
    Base class for TRON DEX streams using TronGrid API.

    Uses REST API polling with filters to efficiently monitor swap events.
    This approach is reliable and works with free TronGrid endpoints.

    Benefits:
    - Free TronGrid API access
    - Reliable event monitoring
    - Configurable polling intervals
    - Event filtering by type
    """

    def __init__(
        self,
        dex_name: str,
        contract_address: str,
        event_name: str = "Swap",
        trongrid_api_key: Optional[str] = None,
        poll_interval: float = 2.0,
        commitment: str = "confirmed",
    ):
        """
        Initialize TRON DEX stream.

        Args:
            dex_name: Name of the DEX (e.g., "sunswap_v3")
            contract_address: TRON contract address to monitor
            event_name: Event name to filter (e.g., "Swap")
            trongrid_api_key: Optional TronGrid API key for higher rate limits
            poll_interval: Seconds between polls (default: 2.0)
            commitment: Transaction confirmation level (confirmed/unconfirmed)
        """
        self.dex_name = dex_name
        self.contract_address = contract_address
        self.event_name = event_name
        self.trongrid_api_key = trongrid_api_key
        self.poll_interval = poll_interval
        self.commitment = commitment

        # TronGrid API base URL
        self.api_base = "https://api.trongrid.io"

        # Callbacks
        self._swap_callbacks: List[Callable] = []
        self._error_callbacks: List[Callable] = []

        # State
        self._running = False
        self._last_timestamp = None
        self._session: Optional[aiohttp.ClientSession] = None

        # Stats
        self._swap_count = 0
        self._parsed_count = 0
        self._error_count = 0
        self._start_time: Optional[datetime] = None

        logger.info(
            f"Initialized {dex_name.upper()} TRON stream "
            f"(contract: {contract_address[:8]}...)"
        )

    def on_swap(self, callback: Callable):
        """Register callback for swap events."""
        self._swap_callbacks.append(callback)

    def on_error(self, callback: Callable):
        """Register callback for error events."""
        self._error_callbacks.append(callback)

    async def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for TronGrid API requests."""
        headers = {"Accept": "application/json"}
        if self.trongrid_api_key:
            headers["TRON-PRO-API-KEY"] = self.trongrid_api_key
        return headers

    async def _fetch_events(self, min_timestamp: Optional[int] = None) -> List[Dict]:
        """
        Fetch contract events from TronGrid API.

        Args:
            min_timestamp: Minimum timestamp in milliseconds

        Returns:
            List of event dictionaries
        """
        if not self._session:
            return []

        try:
            # Build API URL
            url = f"{self.api_base}/v1/contracts/{self.contract_address}/events"

            # Build query parameters
            params = {
                "event_name": self.event_name,
                "only_confirmed": "true" if self.commitment == "confirmed" else "false",
                "limit": 200,  # Max events per request
            }

            if min_timestamp:
                params["min_timestamp"] = min_timestamp

            # Make request
            headers = await self._get_headers()
            async with self._session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", [])
                else:
                    logger.error(
                        f"TronGrid API error: {response.status} - {await response.text()}"
                    )
                    return []

        except Exception as e:
            logger.error(f"Error fetching events from TronGrid: {e}")
            self._error_count += 1
            return []

    def _parse_swap_event(self, event: Dict) -> Optional[Dict]:
        """
        Parse swap event data from TronGrid event.

        Override this method in subclasses to implement DEX-specific parsing.

        Args:
            event: Raw event data from TronGrid

        Returns:
            Parsed swap data or None if parsing fails
        """
        # Base implementation - subclasses should override
        return {
            "raw_event": event,
            "transaction_id": event.get("transaction_id"),
            "block_number": event.get("block_number"),
            "block_timestamp": event.get("block_timestamp"),
            "contract_address": event.get("contract_address"),
            "event_name": event.get("event_name"),
            "result": event.get("result", {}),
        }

    async def _handle_events(self, events: List[Dict]):
        """Process fetched events."""
        for event in events:
            try:
                # Parse swap details
                swap_data = self._parse_swap_event(event)

                if swap_data:
                    self._swap_count += 1
                    self._parsed_count += 1

                    # Update last timestamp
                    block_timestamp = event.get("block_timestamp")
                    if block_timestamp:
                        self._last_timestamp = block_timestamp

                    # Create event data
                    event_data = {
                        "signature": event.get("transaction_id"),
                        "block_number": event.get("block_number"),
                        "block_timestamp": block_timestamp,
                        "swap_details": swap_data,
                        "dex": self.dex_name,
                        "contract_address": self.contract_address,
                    }

                    # Log swap
                    logger.info(
                        f"SWAP {self.dex_name.upper()} #{self._swap_count} | "
                        f"Tx: {event.get('transaction_id', '')[:16]}... | "
                        f"Block: {event.get('block_number')}"
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
                logger.error(f"Error handling event: {e}")
                self._error_count += 1

    async def start(self):
        """
        Start monitoring DEX swaps via TronGrid API polling.
        """
        logger.info(f"Starting {self.dex_name.upper()} TRON stream...")
        self._start_time = datetime.now()
        self._running = True

        # Create aiohttp session
        self._session = aiohttp.ClientSession()

        try:
            # Initialize last timestamp to current time minus poll interval
            if not self._last_timestamp:
                self._last_timestamp = int((datetime.now().timestamp() - self.poll_interval) * 1000)

            logger.info(
                f"Subscribing to {self.dex_name.upper()} contract: {self.contract_address} "
                f"(event: {self.event_name}, interval: {self.poll_interval}s)"
            )

            # Poll for events
            while self._running:
                try:
                    # Fetch events since last timestamp
                    events = await self._fetch_events(min_timestamp=self._last_timestamp)

                    if events:
                        logger.debug(f"Fetched {len(events)} events from {self.dex_name.upper()}")
                        await self._handle_events(events)

                    # Wait before next poll
                    await asyncio.sleep(self.poll_interval)

                except Exception as e:
                    logger.error(f"{self.dex_name.upper()} polling error: {e}")
                    self._error_count += 1
                    await asyncio.sleep(self.poll_interval * 2)  # Back off on error

        except KeyboardInterrupt:
            logger.info(f"Stopping {self.dex_name.upper()} TRON stream...")
        except Exception as e:
            logger.error(f"{self.dex_name.upper()} TRON stream error: {e}")
            self._error_count += 1
            for callback in self._error_callbacks:
                try:
                    callback({"error": str(e), "dex": self.dex_name})
                except Exception as cb_error:
                    logger.error(f"Error callback failed: {cb_error}")
        finally:
            await self.stop()
            self._log_stats()

    async def stop(self):
        """Stop the stream gracefully."""
        self._running = False
        if self._session:
            await self._session.close()
            self._session = None

    def _log_stats(self):
        """Log final statistics."""
        if self._start_time:
            duration = (datetime.now() - self._start_time).total_seconds()
            logger.info(
                f"{self.dex_name.upper()} TRON Stats: "
                f"{self._swap_count} swaps "
                f"({self._parsed_count} parsed), "
                f"{self._error_count} errors, "
                f"{duration:.1f}s runtime"
            )
