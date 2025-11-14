"""
DEX (Decentralized Exchange) real-time stream handler.

Monitors Uniswap V3 pools on Ethereum for real-time swap events.
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

from config.loader import get_uniswap_config, get_pool_abi, get_all_pool_addresses

load_dotenv()

logger = logging.getLogger(__name__)

# Load Uniswap V3 configuration from config/uniswap.yaml
_uniswap_config = get_uniswap_config()
UNISWAP_V3_POOLS = _uniswap_config['pools']
UNISWAP_V3_ROUTER = _uniswap_config['routers']['v3_router']
UNISWAP_V3_SWAP_ROUTER_02 = _uniswap_config['routers']['swap_router_02']
UNISWAP_V3_POOL_ABI = get_pool_abi()


class DEXStream:
    """
    Real-time DEX stream handler for Uniswap V3.

    Monitors multiple Uniswap V3 pools across different fee tiers and stablecoin pairs.
    Provides real-time swap events with accurate price calculations.

    Architecture fit:
    - Part of market_data/stream layer
    - Emits events to event bus (to be integrated)
    - Provides data for analytics engine

    Usage:
        stream = DEXStream(pools=["ETH-USDC-0.3%", "ETH-USDT-0.3%"])
        stream.on_swap(callback_function)
        await stream.start()
    """

    def __init__(
        self,
        alchemy_api_key: Optional[str] = None,
        pools: Optional[List[str]] = None,
        chain: str = "ethereum",
        enable_mempool: bool = True
    ):
        """
        Initialize DEX stream.

        Args:
            alchemy_api_key: Alchemy API key (or set ALCHEMY_API_KEY in .env)
            pools: List of pool names to monitor (default: all major ETH pools)
            chain: Blockchain network (currently only "ethereum" supported)
            enable_mempool: Monitor pending transactions in mempool (default: True)
        """
        self.api_key = alchemy_api_key or os.getenv("ALCHEMY_API_KEY")
        self.chain = chain
        self.enable_mempool = enable_mempool

        if not self.api_key:
            raise ValueError("Alchemy API key required. Set ALCHEMY_API_KEY in .env")

        self.wss_url = f"wss://eth-mainnet.g.alchemy.com/v2/{self.api_key}"

        # Select pools to monitor
        self.pools_to_monitor = pools or list(UNISWAP_V3_POOLS.keys())
        self.pool_configs = {
            name: UNISWAP_V3_POOLS[name]
            for name in self.pools_to_monitor
        }

        self.w3: Optional[AsyncWeb3] = None
        self.pool_contracts = {}
        self.current_prices = {}
        self.swap_callbacks: List[Callable] = []
        self.pending_tx_callbacks: List[Callable] = []
        self.swap_count = 0
        self.pending_tx_count = 0
        self._running = False

    def _calculate_price_from_sqrt(
        self,
        sqrt_price_x96: int,
        pool_config: Dict
    ) -> Decimal:
        """
        Calculate ETH price in USD from Uniswap's sqrtPriceX96.

        The sqrtPriceX96 represents sqrt(token1/token0) in X96 fixed-point format.
        We handle different token orderings to always return USD per ETH.

        Args:
            sqrt_price_x96: Square root of price in X96 format
            pool_config: Pool configuration with token ordering and decimals

        Returns:
            ETH price in USD (Decimal)
        """
        # Convert from X96 fixed-point format
        sqrt_price = Decimal(sqrt_price_x96) / Decimal(2 ** 96)

        # Square to get the ratio: token1/token0
        price_ratio = sqrt_price ** 2

        # Get token info
        token0 = pool_config['token0']
        token1 = pool_config['token1']
        decimals0 = pool_config['decimals0']
        decimals1 = pool_config['decimals1']

        # Adjust for decimals difference
        decimal_adjustment = Decimal(10 ** (decimals0 - decimals1))
        adjusted_price = price_ratio * decimal_adjustment

        # Determine what this price represents and convert to USD per ETH
        if 'WETH' in token1 or 'ETH' in token1:
            # token1 is WETH, token0 is stablecoin
            # adjusted_price = WETH/Stablecoin, so invert to get Stablecoin/WETH
            price_usd_per_eth = Decimal(1) / adjusted_price
        else:
            # token0 is WETH, token1 is stablecoin
            # adjusted_price = Stablecoin/WETH, which is already what we want
            price_usd_per_eth = adjusted_price

        return price_usd_per_eth

    async def connect(self):
        """Connect to Ethereum via Alchemy WebSocket."""
        logger.info(f"Connecting to Ethereum mainnet via Alchemy...")
        logger.info(f"Connecting to: {self.wss_url[:50]}...")

        try:
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

            logger.info("✓ Connected to Ethereum mainnet")

        except asyncio.TimeoutError:
            logger.error("⚠️  Connection to Alchemy timed out after 10 seconds")
            logger.error("⚠️  Check your ALCHEMY_API_KEY in .env file")
            raise ConnectionError("Alchemy WebSocket connection timeout")
        except Exception as e:
            logger.error(f"⚠️  Failed to connect to Alchemy: {e}")
            logger.error(f"⚠️  WebSocket URL: {self.wss_url[:50]}...")
            raise

        # Setup pool contract for initial price
        main_pool_address = UNISWAP_V3_POOLS["ETH-USDC-0.3%"]["address"]
        self.pool_contract = self.w3.eth.contract(
            address=main_pool_address,
            abi=UNISWAP_V3_POOL_ABI
        )

        # Get initial price
        await self._update_current_price()

    async def _update_current_price(self):
        """Fetch current price from main pool's slot0."""
        try:
            slot0 = await self.pool_contract.functions.slot0().call()
            sqrt_price_x96 = slot0[0]

            pool_config = UNISWAP_V3_POOLS["ETH-USDC-0.3%"]
            self.current_price = self._calculate_price_from_sqrt(
                sqrt_price_x96,
                pool_config
            )

            logger.info(f"📊 Current Uniswap V3 ETH/USDC: ${self.current_price:.2f}")

        except Exception as e:
            logger.error(f"Error fetching current price: {e}")

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

            # Ensure address has 0x prefix
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
                    abi=UNISWAP_V3_POOL_ABI
                )

            # Decode event data
            decoded_log = self.pool_contracts[pool_address].events.Swap().process_log(log_receipt)

            # Extract swap data
            sqrt_price_x96 = decoded_log['args']['sqrtPriceX96']
            amount0 = decoded_log['args']['amount0']
            amount1 = decoded_log['args']['amount1']

            # Get token info
            token0 = pool_config['token0']
            token1 = pool_config['token1']
            decimals0 = pool_config['decimals0']
            decimals1 = pool_config['decimals1']

            # Calculate price (always return USD per ETH)
            new_price = self._calculate_price_from_sqrt(sqrt_price_x96, pool_config)

            # Identify ETH amount and stablecoin amount
            if 'WETH' in token1 or 'ETH' in token1:
                # token1 is WETH
                eth_amount = abs(amount1) / 10**decimals1
                stablecoin_amount = abs(amount0) / 10**decimals0
                direction = "SELL" if amount1 < 0 else "BUY"
                stablecoin = token0
            else:
                # token0 is WETH
                eth_amount = abs(amount0) / 10**decimals0
                stablecoin_amount = abs(amount1) / 10**decimals1
                direction = "SELL" if amount0 < 0 else "BUY"
                stablecoin = token1

            # Store current price for this pool
            self.current_prices[pool_name] = new_price

            # Calculate USD value of the trade
            trade_value_usd = eth_amount * float(new_price)

            logger.info(
                f"🔄 Swap #{self.swap_count} [{pool_name}] | {direction} | "
                f"ETH: {eth_amount:.4f} (${trade_value_usd:,.2f}) | "
                f"{stablecoin}: {stablecoin_amount:,.2f} | "
                f"Price: ${new_price:,.2f}"
            )

            # Handle transaction hash (can be bytes or string)
            tx_hash = log_receipt['transactionHash']
            if isinstance(tx_hash, bytes):
                tx_hash_hex = '0x' + tx_hash.hex()
            elif isinstance(tx_hash, str):
                tx_hash_hex = tx_hash if tx_hash.startswith('0x') else '0x' + tx_hash
            else:
                tx_hash_hex = str(tx_hash)

            # Prepare swap data
            swap_data = {
                'exchange': 'UNISWAP_V3',
                'pool': pool_name,
                'price': new_price,
                'eth_amount': Decimal(str(eth_amount)),
                'stablecoin_amount': Decimal(str(stablecoin_amount)),
                'stablecoin': stablecoin,
                'trade_value_usd': Decimal(str(trade_value_usd)),
                'direction': direction,
                'timestamp': datetime.now(),
                'tx_hash': tx_hash_hex,
                'chain': self.chain,
            }

            # Notify callbacks
            await self._notify_callbacks(swap_data)

        except Exception as e:
            logger.error(f"Error processing swap event: {e}")

    async def _handle_pending_transaction(self, tx_hash: str):
        """Process a pending transaction from mempool."""
        try:
            # Fetch transaction details
            tx = await self.w3.eth.get_transaction(tx_hash)

            if not tx or not tx.get('to'):
                return

            # Check if transaction is to one of our monitored pools
            to_address = tx['to'].lower() if tx['to'] else None

            pool_name = None
            pool_config = None

            for name, config in self.pool_configs.items():
                if config['address'].lower() == to_address:
                    pool_name = name
                    pool_config = config
                    break

            # Also check router addresses
            if not pool_name:
                router_addresses = [
                    UNISWAP_V3_ROUTER.lower(),
                    UNISWAP_V3_SWAP_ROUTER_02.lower()
                ]
                if to_address not in router_addresses:
                    return  # Not a Uniswap transaction

            self.pending_tx_count += 1

            # Extract basic transaction info
            value_eth = float(tx.get('value', 0)) / 1e18
            gas_price_gwei = float(tx.get('gasPrice', 0)) / 1e9 if tx.get('gasPrice') else 0
            max_priority_fee = float(tx.get('maxPriorityFeePerGas', 0)) / 1e9 if tx.get('maxPriorityFeePerGas') else 0

            pending_tx_data = {
                'exchange': 'UNISWAP_V3',
                'pool': pool_name or 'ROUTER',
                'tx_hash': tx_hash if tx_hash.startswith('0x') else '0x' + tx_hash,
                'from': tx.get('from'),
                'to': to_address,
                'value_eth': Decimal(str(value_eth)),
                'gas_price_gwei': Decimal(str(gas_price_gwei)),
                'max_priority_fee_gwei': Decimal(str(max_priority_fee)),
                'input_data': tx.get('input', '0x'),
                'timestamp': datetime.now(),
                'chain': self.chain,
                'status': 'pending'
            }

            # Tiered logging based on significance
            if value_eth > 10.0:
                logger.warning(
                    f"🐋 WHALE TX #{self.pending_tx_count} | "
                    f"Pool: {pool_name or 'ROUTER'} | "
                    f"Value: {value_eth:.4f} ETH | "
                    f"Gas: {gas_price_gwei:.2f} Gwei | "
                    f"TX: {tx_hash[:16]}..."
                )
            elif value_eth > 1.0:
                logger.info(
                    f"⏳ Large TX #{self.pending_tx_count} | "
                    f"Pool: {pool_name or 'ROUTER'} | "
                    f"Value: {value_eth:.4f} ETH | "
                    f"Gas: {gas_price_gwei:.2f} Gwei"
                )
            else:
                # Still log in debug mode for full visibility
                logger.debug(
                    f"⏳ TX #{self.pending_tx_count} | "
                    f"Pool: {pool_name or 'ROUTER'} | "
                    f"Value: {value_eth:.4f} ETH"
                )

            # ALWAYS notify callbacks regardless of size - let strategy decide
            await self._notify_pending_tx_callbacks(pending_tx_data)

        except Exception as e:
            # Don't log every error (mempool has many invalid/failed txs)
            logger.debug(f"Error processing pending tx {tx_hash[:16]}...: {e}")

    async def subscribe_to_mempool(self):
        """Subscribe to pending transactions in mempool."""
        logger.info("🔮 Subscribing to Ethereum mempool (pending transactions)...")

        try:
            subscription_id = await self.w3.eth.subscribe("newPendingTransactions")
            logger.info(f"✓ Subscribed to mempool (ID: {subscription_id})")
        except Exception as e:
            logger.error(f"Mempool subscription failed: {e}")
            raise

        # Listen for pending transactions
        async for payload in self.w3.socket.process_subscriptions():
            if not self._running:
                break

            try:
                tx_hash = payload["result"]
                # Process pending transaction asynchronously (don't block stream)
                asyncio.create_task(self._handle_pending_transaction(tx_hash))
            except Exception as e:
                logger.debug(f"Error receiving pending tx: {e}")

    async def subscribe_to_swaps(self):
        """Subscribe to Uniswap V3 swap events for all monitored pools."""
        logger.info(f"Subscribing to {len(self.pool_configs)} Uniswap V3 pools...")

        # Get Swap event topic
        swap_event_topic = self.w3.keccak(
            text="Swap(address,address,int256,int256,uint160,uint128,int24)"
        ).hex()
        if not swap_event_topic.startswith('0x'):
            swap_event_topic = '0x' + swap_event_topic

        # Get all pool addresses to monitor
        pool_addresses = [
            self.w3.to_checksum_address(config["address"])
            for config in self.pool_configs.values()
        ]

        # Create filter params to monitor ALL pools at once
        filter_params = {
            "address": pool_addresses,
            "topics": [swap_event_topic]
        }

        logger.info(f"Monitoring pools: {', '.join(self.pools_to_monitor)}")

        try:
            subscription_id = await self.w3.eth.subscribe("logs", filter_params)
            logger.info(f"✓ Subscribed to real-time DEX swaps (ID: {subscription_id})")
        except Exception as e:
            logger.error(f"Subscription failed: {e}")
            raise

        logger.info(f"✓ Monitoring {len(pool_addresses)} Uniswap V3 pools")

        # Listen for swap events
        async for payload in self.w3.socket.process_subscriptions():
            if not self._running:
                break

            try:
                result = payload["result"]
                await self._handle_swap_log(result)
            except Exception as e:
                logger.error(f"Error receiving swap event: {e}")

    async def _notify_callbacks(self, swap_data: Dict):
        """Notify all registered callbacks of new swap."""
        for callback in self.swap_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(swap_data)
                else:
                    callback(swap_data)
            except Exception as e:
                logger.error(f"Error in swap callback: {e}")

    async def _notify_pending_tx_callbacks(self, tx_data: Dict):
        """Notify all registered callbacks of pending transaction."""
        for callback in self.pending_tx_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(tx_data)
                else:
                    callback(tx_data)
            except Exception as e:
                logger.error(f"Error in pending tx callback: {e}")

    def on_swap(self, callback: Callable):
        """
        Register callback for DEX swap events.

        Args:
            callback: Function(swap_data) - called on each swap

        Example:
            async def my_handler(data):
                print(f"Swap: {data['pool']} @ ${data['price']}")

            stream.on_swap(my_handler)
        """
        self.swap_callbacks.append(callback)

    def on_pending_tx(self, callback: Callable):
        """
        Register callback for pending transaction events.

        Args:
            callback: Function(tx_data) - called on each pending tx

        Example:
            async def my_handler(data):
                print(f"Pending: {data['pool']} | {data['value_eth']} ETH")

            stream.on_pending_tx(my_handler)
        """
        self.pending_tx_callbacks.append(callback)

    async def start(self):
        """Start DEX stream."""
        self._running = True
        await self.connect()

        # Start both subscriptions concurrently
        tasks = [asyncio.create_task(self.subscribe_to_swaps())]

        if self.enable_mempool:
            tasks.append(asyncio.create_task(self.subscribe_to_mempool()))
            logger.info("✓ Mempool monitoring enabled")
        else:
            logger.info("⚠️  Mempool monitoring disabled")

        # Wait for both subscriptions to complete
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self):
        """Stop DEX stream."""
        self._running = False
        if self.w3 and hasattr(self.w3.provider, 'disconnect'):
            await self.w3.provider.disconnect()
        logger.info("DEX stream stopped")


# Example usage
async def main():
    """Example: Monitor Uniswap V3 swaps in real-time."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Create DEX stream
    stream = DEXStream(pools=["ETH-USDC-0.3%", "ETH-USDT-0.3%", "ETH-DAI-0.3%"])

    # Register callback
    async def handle_swap(data):
        """Handle swap events."""
        print(f"\n💎 {data['exchange']} {data['pool']}: ${data['price']:.2f}")
        print(f"   Direction: {data['direction']}")
        print(f"   Volume: {data['eth_amount']:.4f} ETH")
        print(f"   TX: {data['tx_hash'][:16]}...")

    stream.on_swap(handle_swap)

    # Start stream
    try:
        await stream.start()
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        await stream.stop()


if __name__ == "__main__":
    asyncio.run(main())
