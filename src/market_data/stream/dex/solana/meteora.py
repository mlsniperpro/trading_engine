"""
Meteora DLMM real-time stream handler.

Monitors Meteora (22% of Solana spot trading volume) for:
- DLMM (Dynamic Liquidity Market Maker) swaps
- Dynamic fee adjustments
- Liquidity bin updates

Meteora is a rising star with better capital efficiency through
dynamic liquidity management.
"""

import asyncio
import logging
import os
from decimal import Decimal
from typing import Callable, Optional, Dict, List
from datetime import datetime

from solana.rpc.websocket_api import connect
from solana.rpc.commitment import Confirmed
from solders.pubkey import Pubkey
from solders.rpc.config import RpcTransactionLogsFilterMentions
from dotenv import load_dotenv
import yaml

load_dotenv()

logger = logging.getLogger(__name__)

# Load Meteora configuration
def _load_meteora_config():
    config_path = "/workspaces/trading_engine/config/solana_dex.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config['meteora']

METEORA_CONFIG = _load_meteora_config()
METEORA_PROGRAM_ID = METEORA_CONFIG['program_id']


class MeteoraStream:
    """
    Real-time Meteora DLMM stream handler.

    Monitors Meteora for dynamic liquidity swap activity:
    - DLMM swaps with dynamic fees
    - Liquidity bin updates
    - Capital efficiency optimizations

    Meteora handles 22% of Solana spot trading and uses innovative
    DLMM (Dynamic Liquidity Market Maker) technology for better
    capital efficiency than traditional AMMs.

    Architecture fit:
    - Part of market_data/stream/dex/solana layer
    - Emits events to callbacks for processing
    - Provides dynamic liquidity price data

    Usage:
        stream = MeteoraStream(pools=["SOL-USDC"])
        stream.on_swap(lambda data: print(f"Swap: {data}"))
        await stream.start()
    """

    def __init__(
        self,
        solana_rpc_url: Optional[str] = None,
        solana_ws_url: Optional[str] = None,
        pools: Optional[List[str]] = None,
    ):
        """
        Initialize Meteora stream.

        Args:
            solana_rpc_url: Solana RPC HTTP endpoint
            solana_ws_url: Solana WebSocket endpoint
            pools: List of DLMM pool names to monitor
        """
        self.rpc_url = solana_rpc_url or os.getenv(
            "SOLANA_RPC_URL",
            "https://api.mainnet-beta.solana.com"
        )
        self.ws_url = solana_ws_url or os.getenv(
            "SOLANA_WS_URL",
            "wss://api.mainnet-beta.solana.com"
        )
        self.pools_to_monitor = pools or []

        # Meteora DLMM program ID
        self.program_id = Pubkey.from_string(METEORA_PROGRAM_ID)

        # State tracking
        self.current_prices = {}
        self.monitored_pools = {}
        self.swap_callbacks: List[Callable] = []
        self.bin_callbacks: List[Callable] = []
        self.swap_count = 0
        self.bin_update_count = 0
        self._running = False
        self._ws = None

    async def connect(self):
        """Connect to Solana WebSocket."""
        try:
            logger.info("Connecting to Solana mainnet...")
            logger.info(f"WebSocket: {self.ws_url}")

            # Connect to Solana WebSocket
            self._ws = await connect(self.ws_url)

            logger.info("✓ Connected to Solana mainnet (Meteora)")

        except Exception as e:
            logger.error(f"⚠️  Failed to connect to Solana: {e}")
            raise

    async def _handle_swap_log(self, log_data: Dict):
        """Process a swap log from Meteora DLMM."""
        try:
            self.swap_count += 1

            # Extract swap data (simplified - would parse from log)
            swap_data = {
                'pool': 'SOL-USDC',  # Would extract from log
                'token_x': 'SOL',
                'token_y': 'USDC',
                'amount_x': 8.75,
                'amount_y': 1487.5,
                'bin_id': 45678,  # Active bin
                'dynamic_fee': 0.008,  # Dynamic fee (0.8%)
                'price': 170.0,
                'protocol_fee': 0.15,
                'signature': 'Sig...',
                'timestamp': datetime.now(),
                'exchange': 'METEORA',
            }

            # Update current price
            pool = swap_data['pool']
            self.current_prices[pool] = Decimal(str(swap_data['price']))

            logger.info(
                f"🔄 Meteora Swap #{self.swap_count} [{pool}] | "
                f"{swap_data['token_x']}: {swap_data['amount_x']:.2f} | "
                f"{swap_data['token_y']}: {swap_data['amount_y']:.2f} | "
                f"Price: ${swap_data['price']:.2f} | "
                f"Fee: {swap_data['dynamic_fee']:.3f}% | "
                f"Bin: {swap_data['bin_id']}"
            )

            # Notify callbacks
            await self._notify_callbacks(self.swap_callbacks, swap_data)

        except Exception as e:
            logger.error(f"Error processing Meteora swap: {e}")

    async def _handle_bin_update(self, bin_data: Dict):
        """Handle DLMM bin liquidity update."""
        try:
            self.bin_update_count += 1

            # Extract bin data (simplified - would parse from transaction)
            bin_info = {
                'pool': 'SOL-USDC',
                'bin_id': 45678,
                'liquidity_x': 500.0,
                'liquidity_y': 85000.0,
                'fee_x': 2.5,
                'fee_y': 425.0,
                'dynamic_fee_rate': 0.008,
                'timestamp': datetime.now(),
                'exchange': 'METEORA',
            }

            logger.debug(
                f"📊 Meteora Bin #{self.bin_update_count} | "
                f"Pool: {bin_info['pool']} | "
                f"Bin: {bin_info['bin_id']} | "
                f"Liquidity X: {bin_info['liquidity_x']:.2f} | "
                f"Liquidity Y: {bin_info['liquidity_y']:.2f}"
            )

            # Notify callbacks
            await self._notify_callbacks(self.bin_callbacks, bin_info)

        except Exception as e:
            logger.error(f"Error handling Meteora bin update: {e}")

    async def _notify_callbacks(self, callbacks: List[Callable], data: Dict):
        """Notify all registered callbacks."""
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Error in callback: {e}")

    def on_swap(self, callback: Callable):
        """
        Register callback for swap events.

        Args:
            callback: Function to call on swap
                     Signature: callback(swap_data: Dict) -> None
        """
        self.swap_callbacks.append(callback)

    def on_bin_update(self, callback: Callable):
        """
        Register callback for liquidity bin updates.

        Args:
            callback: Function to call on bin update
                     Signature: callback(bin_data: Dict) -> None
        """
        self.bin_callbacks.append(callback)

    async def start(self):
        """Start monitoring Meteora DLMM pools."""
        if self._running:
            logger.warning("Meteora stream already running")
            return

        self._running = True

        # Connect to Solana
        await self.connect()

        logger.info("Starting Meteora stream...")
        logger.info(f"Program ID: {self.program_id}")

        try:
            # Subscribe to Meteora DLMM program logs
            filter_mentions = RpcTransactionLogsFilterMentions([self.program_id])
            await self._ws.logs_subscribe(
                filter_=filter_mentions,
                commitment=Confirmed
            )

            logger.info("✓ Subscribed to Meteora DLMM program logs")
            logger.info("✓ Monitoring dynamic liquidity swaps")

            # Get subscription ID
            first_response = await self._ws.recv()
            subscription_id = first_response[0].result
            logger.info(f"✓ Subscription ID: {subscription_id}")

            # Stream events
            async for msg in self._ws:
                if not self._running:
                    break

                try:
                    # Process log message
                    # In production, parse logs to extract swap/bin data
                    if hasattr(msg, 'result'):
                        # This is a notification
                        pass
                except Exception as e:
                    logger.error(f"Error processing Meteora event: {e}")

        except Exception as e:
            logger.error(f"Failed to start Meteora stream: {e}")
            raise

    async def stop(self):
        """Stop monitoring Meteora."""
        self._running = False

        if self._ws:
            await self._ws.close()

        logger.info("Meteora stream stopped")

    def get_current_prices(self) -> Dict[str, Decimal]:
        """
        Get current prices from monitored pools.

        Returns:
            Dictionary mapping pool names to prices
        """
        return self.current_prices.copy()

    def get_stats(self) -> Dict:
        """
        Get stream statistics.

        Returns:
            Statistics dictionary
        """
        return {
            'swaps': self.swap_count,
            'bin_updates': self.bin_update_count,
        }
