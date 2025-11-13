"""
Curve Finance real-time stream handler.

Monitors Curve pools on Ethereum for real-time swap events.
Connects directly to blockchain via Alchemy WebSocket.
"""

import asyncio
import logging
import os
from decimal import Decimal
from typing import Callable, Optional, Dict, List
from datetime import datetime

from web3 import AsyncWeb3
from web3.providers import WebSocketProvider
from dotenv import load_dotenv

from config.loader import get_curve_config

load_dotenv()

logger = logging.getLogger(__name__)

# Load Curve configuration
_curve_config = get_curve_config()
CURVE_POOLS = _curve_config['pools']
CURVE_ROUTER = _curve_config['router']

# Curve Pool ABI (TokenExchange event - Curve's swap event)
CURVE_POOL_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "buyer", "type": "address"},
            {"indexed": False, "name": "sold_id", "type": "int128"},
            {"indexed": False, "name": "tokens_sold", "type": "uint256"},
            {"indexed": False, "name": "bought_id", "type": "int128"},
            {"indexed": False, "name": "tokens_bought", "type": "uint256"}
        ],
        "name": "TokenExchange",
        "type": "event"
    },
    {
        "name": "get_dy",
        "outputs": [{"type": "uint256", "name": ""}],
        "inputs": [
            {"type": "int128", "name": "i"},
            {"type": "int128", "name": "j"},
            {"type": "uint256", "name": "dx"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]


class CurveStream:
    """
    Real-time Curve Finance stream handler.

    Monitors Curve pools for swap events. Curve is specialized for stablecoin swaps
    and liquid staking derivatives (stETH, frxETH).

    Architecture fit:
    - Part of market_data/stream layer
    - Emits events to event bus (to be integrated)
    - Provides data for analytics engine

    Usage:
        stream = CurveStream(pools=["3pool", "stETH"])
        stream.on_swap(callback_function)
        await stream.start()
    """

    def __init__(
        self,
        alchemy_api_key: Optional[str] = None,
        pools: Optional[List[str]] = None,
        chain: str = "ethereum"
    ):
        """
        Initialize Curve stream.

        Args:
            alchemy_api_key: Alchemy API key (or set ALCHEMY_API_KEY in .env)
            pools: List of pool names to monitor (default: all major pools)
            chain: Blockchain network (currently only "ethereum" supported)
        """
        self.api_key = alchemy_api_key or os.getenv("ALCHEMY_API_KEY")
        self.chain = chain

        if not self.api_key:
            raise ValueError("Alchemy API key required. Set ALCHEMY_API_KEY in .env")

        self.wss_url = f"wss://eth-mainnet.g.alchemy.com/v2/{self.api_key}"

        # Select pools to monitor
        self.pools_to_monitor = pools or list(CURVE_POOLS.keys())
        self.pool_configs = {
            name: CURVE_POOLS[name]
            for name in self.pools_to_monitor
        }

        self.w3: Optional[AsyncWeb3] = None
        self.pool_contracts = {}
        self.current_prices = {}
        self.swap_callbacks: List[Callable] = []
        self.swap_count = 0
        self._running = False

    def _calculate_price(self, pool_config: Dict, sold_id: int, bought_id: int,
                        tokens_sold: int, tokens_bought: int) -> Optional[Decimal]:
        """
        Calculate price from Curve swap.

        For ETH pools (stETH, frxETH), returns ETH price.
        For stablecoin pools, returns relative stablecoin price.

        Args:
            pool_config: Pool configuration
            sold_id: Index of token sold
            bought_id: Index of token bought
            tokens_sold: Amount of tokens sold (raw)
            tokens_bought: Amount of tokens bought (raw)

        Returns:
            Price or None if not ETH-related
        """
        coins = pool_config['coins']
        decimals = pool_config['decimals']

        # Get token names
        sold_token = coins[sold_id]
        bought_token = coins[bought_id]

        # Adjust for decimals
        sold_amount = Decimal(tokens_sold) / Decimal(10 ** decimals[sold_id])
        bought_amount = Decimal(tokens_bought) / Decimal(10 ** decimals[bought_id])

        # Calculate exchange rate
        if sold_amount > 0:
            rate = bought_amount / sold_amount
        else:
            return None

        # For ETH/stETH pools, we care about the peg
        # For stablecoin pools, we don't track USD price (it's always ~$1)
        if 'ETH' in sold_token or 'ETH' in bought_token:
            # Return the ratio (should be close to 1.0 for pegged assets)
            return rate

        return None

    async def connect(self):
        """Connect to Ethereum via Alchemy WebSocket."""
        try:
            logger.info("Connecting to Ethereum mainnet via Alchemy...")
            logger.info(f"Connecting to: {self.wss_url[:50]}...")

            provider = WebSocketProvider(
                self.wss_url,
                websocket_timeout=60,
                websocket_kwargs={'max_size': 2**25}
            )

            self.w3 = AsyncWeb3(provider)

            # Test connection with timeout
            connected = await asyncio.wait_for(
                self.w3.is_connected(),
                timeout=10.0
            )

            if not connected:
                raise ConnectionError("Failed to connect to Ethereum WebSocket")

            logger.info("✓ Connected to Ethereum mainnet (Curve)")

        except asyncio.TimeoutError:
            logger.error("⚠️  Connection to Alchemy timed out after 10 seconds")
            raise ConnectionError("Alchemy WebSocket connection timeout")
        except Exception as e:
            logger.error(f"⚠️  Failed to connect to Alchemy: {e}")
            raise

    async def _handle_swap_log(self, log_receipt):
        """Process a single swap log event."""
        try:
            self.swap_count += 1

            # Identify which pool this swap is from
            raw_address = log_receipt['address']
            if isinstance(raw_address, bytes):
                pool_address = '0x' + raw_address.hex().lower()
            else:
                pool_address = raw_address.lower()

            if not pool_address.startswith('0x'):
                pool_address = '0x' + pool_address

            pool_name = None
            pool_config = None

            for name, config in self.pool_configs.items():
                if config['address'].lower() == pool_address:
                    pool_name = name
                    pool_config = config
                    break

            if not pool_config:
                logger.debug(f"Ignoring swap from unknown pool: {pool_address}")
                return

            # Get pool contract (create if not exists)
            if pool_address not in self.pool_contracts:
                checksum_address = self.w3.to_checksum_address(pool_address)
                self.pool_contracts[pool_address] = self.w3.eth.contract(
                    address=checksum_address,
                    abi=CURVE_POOL_ABI
                )

            # Decode event data
            decoded_log = self.pool_contracts[pool_address].events.TokenExchange().process_log(log_receipt)

            # Extract swap data
            sold_id = decoded_log['args']['sold_id']
            bought_id = decoded_log['args']['bought_id']
            tokens_sold = decoded_log['args']['tokens_sold']
            tokens_bought = decoded_log['args']['tokens_bought']

            # Get token info
            coins = pool_config['coins']
            decimals = pool_config['decimals']

            sold_token = coins[sold_id]
            bought_token = coins[bought_id]
            sold_amount = Decimal(tokens_sold) / Decimal(10 ** decimals[sold_id])
            bought_amount = Decimal(tokens_bought) / Decimal(10 ** decimals[bought_id])

            # Calculate price/rate
            price = self._calculate_price(
                pool_config, sold_id, bought_id,
                tokens_sold, tokens_bought
            )

            if price:
                self.current_prices[pool_name] = price

            # Determine direction
            direction = f"{sold_token} → {bought_token}"

            # Handle transaction hash
            tx_hash = log_receipt['transactionHash']
            if isinstance(tx_hash, bytes):
                tx_hash_hex = '0x' + tx_hash.hex()
            elif isinstance(tx_hash, str):
                tx_hash_hex = tx_hash if tx_hash.startswith('0x') else '0x' + tx_hash
            else:
                tx_hash_hex = str(tx_hash)

            logger.info(
                f"🔄 Curve Swap #{self.swap_count} [{pool_name}] | {direction} | "
                f"Sold: {sold_amount:.4f} {sold_token} | "
                f"Bought: {bought_amount:.4f} {bought_token}"
            )

            # Prepare swap data
            swap_data = {
                'price': price,
                'sold_token': sold_token,
                'bought_token': bought_token,
                'sold_amount': sold_amount,
                'bought_amount': bought_amount,
                'direction': direction,
                'exchange': 'CURVE',
                'pool': pool_name,
                'timestamp': datetime.now(),
                'tx_hash': tx_hash_hex
            }

            # Notify callbacks
            await self._notify_callbacks(swap_data)

        except Exception as e:
            logger.error(f"Error processing Curve swap event: {e}")

    async def _notify_callbacks(self, swap_data: Dict):
        """Notify all registered callbacks of a new swap."""
        for callback in self.swap_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(swap_data)
                else:
                    callback(swap_data)
            except Exception as e:
                logger.error(f"Error in swap callback: {e}")

    def on_swap(self, callback: Callable):
        """
        Register a callback for swap events.

        Args:
            callback: Function to call when a swap occurs
                     Signature: callback(swap_data: Dict) -> None
        """
        self.swap_callbacks.append(callback)

    async def start(self):
        """Start monitoring Curve pools."""
        if self._running:
            logger.warning("Curve stream already running")
            return

        self._running = True

        # Connect to Ethereum
        await self.connect()

        # Get all pool addresses
        pool_addresses = [
            self.w3.to_checksum_address(config['address'])
            for config in self.pool_configs.values()
        ]

        logger.info(f"Starting Curve stream for {len(pool_addresses)} pools...")
        logger.info(f"Monitoring: {', '.join(self.pools_to_monitor)}")

        # Subscribe to TokenExchange events from all pools
        try:
            event_filter = await self.w3.eth.filter({
                'address': pool_addresses,
                'topics': [
                    # TokenExchange event signature
                    self.w3.keccak(text='TokenExchange(address,int128,uint256,int128,uint256)').hex()
                ]
            })

            logger.info("✓ Subscribed to Curve TokenExchange events")

            # Poll for new events
            while self._running:
                try:
                    new_logs = await event_filter.get_new_entries()

                    for log in new_logs:
                        await self._handle_swap_log(log)

                    await asyncio.sleep(1)  # Poll every second

                except Exception as e:
                    logger.error(f"Error polling Curve events: {e}")
                    await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Failed to subscribe to Curve events: {e}")
            raise

    async def stop(self):
        """Stop monitoring Curve pools."""
        self._running = False

        if self.w3 and self.w3.provider:
            await self.w3.provider.disconnect()

        logger.info("Curve stream stopped")

    def get_current_prices(self) -> Dict[str, Decimal]:
        """
        Get current prices from all monitored pools.

        Returns:
            Dictionary mapping pool names to current prices
        """
        return self.current_prices.copy()
