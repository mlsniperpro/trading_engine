"""
Balancer V2 real-time stream handler.

Monitors Balancer V2 pools on Ethereum for real-time swap events.
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

from config.loader import get_balancer_config

load_dotenv()

logger = logging.getLogger(__name__)

# Load Balancer configuration
_balancer_config = get_balancer_config()
BALANCER_POOLS = _balancer_config['pools']
BALANCER_VAULT = _balancer_config['vault']

# Balancer V2 Vault ABI (Swap event - all swaps go through the vault)
BALANCER_VAULT_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "poolId", "type": "bytes32"},
            {"indexed": True, "name": "tokenIn", "type": "address"},
            {"indexed": True, "name": "tokenOut", "type": "address"},
            {"indexed": False, "name": "amountIn", "type": "uint256"},
            {"indexed": False, "name": "amountOut", "type": "uint256"}
        ],
        "name": "Swap",
        "type": "event"
    },
    {
        "inputs": [{"name": "poolId", "type": "bytes32"}],
        "name": "getPoolTokens",
        "outputs": [
            {"name": "tokens", "type": "address[]"},
            {"name": "balances", "type": "uint256[]"},
            {"name": "lastChangeBlock", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]


class BalancerStream:
    """
    Real-time Balancer V2 stream handler.

    Monitors Balancer V2 pools for swap events. Balancer V2 uses a single Vault
    contract for all pools, with support for weighted pools and stable pools.

    Architecture fit:
    - Part of market_data/stream layer
    - Emits events to event bus (to be integrated)
    - Provides data for analytics engine

    Usage:
        stream = BalancerStream(pools=["BAL-WETH", "stable-USD"])
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
        Initialize Balancer stream.

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
        self.pools_to_monitor = pools or list(BALANCER_POOLS.keys())
        self.pool_configs = {
            name: BALANCER_POOLS[name]
            for name in self.pools_to_monitor
        }

        # Create pool_id to name mapping
        self.pool_id_to_name = {
            config['pool_id']: name
            for name, config in self.pool_configs.items()
        }

        self.w3: Optional[AsyncWeb3] = None
        self.vault_contract = None
        self.current_prices = {}
        self.swap_callbacks: List[Callable] = []
        self.swap_count = 0
        self._running = False

    def _calculate_price(self, pool_config: Dict, token_in: str, token_out: str,
                        amount_in: int, amount_out: int) -> Optional[Decimal]:
        """
        Calculate price from Balancer swap.

        For ETH pools, returns ETH price.
        For stablecoin pools, returns relative price.

        Args:
            pool_config: Pool configuration
            token_in: Token being sold
            token_out: Token being bought
            amount_in: Amount sold (raw)
            amount_out: Amount bought (raw)

        Returns:
            Price or None if not relevant
        """
        tokens = pool_config['tokens']
        decimals = pool_config['decimals']

        # Find token indices (we need to match addresses)
        # For now, we'll use simple token name matching
        # In production, you'd match by address

        # Adjust for decimals (assuming standard decimals for now)
        amount_in_adjusted = Decimal(amount_in) / Decimal(10 ** 18)
        amount_out_adjusted = Decimal(amount_out) / Decimal(10 ** 18)

        # Calculate exchange rate
        if amount_in_adjusted > 0:
            rate = amount_out_adjusted / amount_in_adjusted
        else:
            return None

        return rate

    async def connect(self):
        """Connect to Ethereum via Alchemy WebSocket."""
        try:
            logger.info("Connecting to Ethereum mainnet via Alchemy...")
            logger.info(f"Connecting to: {self.wss_url[:50]}...")

            provider = WebSocketProvider(self.wss_url)
            self.w3 = AsyncWeb3(provider)

            # Add timeout to connection attempt
            await asyncio.wait_for(
                self.w3.provider.connect(),
                timeout=10.0
            )

            is_connected = await self.w3.is_connected()
            if not is_connected:
                raise ConnectionError("Failed to connect to Ethereum WebSocket")

            logger.info("✓ Connected to Ethereum mainnet (Balancer)")

            # Setup vault contract
            vault_address = self.w3.to_checksum_address(BALANCER_VAULT)
            self.vault_contract = self.w3.eth.contract(
                address=vault_address,
                abi=BALANCER_VAULT_ABI
            )

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

            # Decode event data
            decoded_log = self.vault_contract.events.Swap().process_log(log_receipt)

            # Extract swap data
            pool_id = decoded_log['args']['poolId'].hex()
            token_in = decoded_log['args']['tokenIn']
            token_out = decoded_log['args']['tokenOut']
            amount_in = decoded_log['args']['amountIn']
            amount_out = decoded_log['args']['amountOut']

            # Find pool name from pool_id
            pool_name = self.pool_id_to_name.get(pool_id)

            if not pool_name:
                logger.debug(f"Ignoring swap from unknown pool: {pool_id[:16]}...")
                return

            pool_config = self.pool_configs[pool_name]

            # Calculate amounts (using 18 decimals as default)
            # In production, you'd fetch actual decimals per token
            amount_in_adjusted = Decimal(amount_in) / Decimal(10 ** 18)
            amount_out_adjusted = Decimal(amount_out) / Decimal(10 ** 18)

            # Calculate price/rate
            price = self._calculate_price(
                pool_config, token_in, token_out,
                amount_in, amount_out
            )

            if price:
                self.current_prices[pool_name] = price

            # Determine direction
            direction = f"Token In → Token Out"

            # Handle transaction hash
            tx_hash = log_receipt['transactionHash']
            if isinstance(tx_hash, bytes):
                tx_hash_hex = '0x' + tx_hash.hex()
            elif isinstance(tx_hash, str):
                tx_hash_hex = tx_hash if tx_hash.startswith('0x') else '0x' + tx_hash
            else:
                tx_hash_hex = str(tx_hash)

            logger.info(
                f"🔄 Balancer Swap #{self.swap_count} [{pool_name}] | "
                f"In: {amount_in_adjusted:.4f} | Out: {amount_out_adjusted:.4f} | "
                f"Rate: {price:.4f if price else 'N/A'}"
            )

            # Prepare swap data
            swap_data = {
                'price': price,
                'pool_id': pool_id,
                'token_in': token_in,
                'token_out': token_out,
                'amount_in': amount_in_adjusted,
                'amount_out': amount_out_adjusted,
                'direction': direction,
                'exchange': 'BALANCER',
                'pool': pool_name,
                'timestamp': datetime.now(),
                'tx_hash': tx_hash_hex
            }

            # Notify callbacks
            await self._notify_callbacks(swap_data)

        except Exception as e:
            logger.error(f"Error processing Balancer swap event: {e}")

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
        """Start monitoring Balancer pools."""
        if self._running:
            logger.warning("Balancer stream already running")
            return

        self._running = True

        # Connect to Ethereum
        await self.connect()

        # Get all pool IDs we're monitoring
        pool_ids = [config['pool_id'] for config in self.pool_configs.values()]

        logger.info(f"Starting Balancer stream for {len(pool_ids)} pools...")
        logger.info(f"Monitoring: {', '.join(self.pools_to_monitor)}")

        # Subscribe to Swap events from the Vault
        try:
            # Get Swap event topic
            swap_event_topic = self.w3.keccak(
                text='Swap(bytes32,address,address,uint256,uint256)'
            ).hex()

            # Create filter params for WebSocket subscription
            # Note: We subscribe to all Vault swaps and filter by pool_id in code
            filter_params = {
                'address': self.w3.to_checksum_address(BALANCER_VAULT),
                'topics': [swap_event_topic]
            }

            # Subscribe using WebSocket
            subscription_id = await self.w3.eth.subscribe("logs", filter_params)
            logger.info(f"✓ Subscribed to Balancer Vault Swap events (ID: {subscription_id})")
            logger.info(f"✓ Monitoring {len(pool_ids)} Balancer pools")

            # Stream events in real-time
            async for payload in self.w3.socket.process_subscriptions():
                if not self._running:
                    break

                try:
                    result = payload["result"]
                    await self._handle_swap_log(result)
                except Exception as e:
                    logger.error(f"Error receiving Balancer swap event: {e}")

        except Exception as e:
            logger.error(f"Failed to subscribe to Balancer events: {e}")
            raise

    async def stop(self):
        """Stop monitoring Balancer pools."""
        self._running = False

        if self.w3 and self.w3.provider:
            await self.w3.provider.disconnect()

        logger.info("Balancer stream stopped")

    def get_current_prices(self) -> Dict[str, Decimal]:
        """
        Get current prices from all monitored pools.

        Returns:
            Dictionary mapping pool names to current prices
        """
        return self.current_prices.copy()
