"""
Real-time DEX (Decentralized Exchange) price feed using Alchemy + Web3.
Monitors Uniswap v3 swaps for ETH/USDC price data.

CURRENT STATUS (2025-11-12):
✓ WebSocket connection to Alchemy works
✓ HTTP connection verified with valid API key
✓ Contract setup and price fetching works
⚠ eth_subscribe for logs has compatibility issue - investigating
  Error: "Invalid logs options in second param to eth_subscribe"

TODO: Debug subscription issue or implement HTTP polling fallback
"""

import asyncio
import logging
import os
from decimal import Decimal
from typing import Callable, Optional, Dict
from datetime import datetime

from web3 import AsyncWeb3
from web3.providers import WebSocketProvider
from web3.utils.subscriptions import LogsSubscription
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# Uniswap V3 Major ETH Pools
UNISWAP_V3_POOLS = {
    "ETH-USDC-0.3%": {
        "address": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
        "token0": "USDC",
        "token1": "WETH",
        "decimals0": 6,
        "decimals1": 18,
    },
    "ETH-USDC-0.05%": {
        "address": "0x7BeA39867e4169DBe237d55C8242a8f2fcDcc387",
        "token0": "USDC",
        "token1": "WETH",
        "decimals0": 6,
        "decimals1": 18,
    },
    "ETH-USDT-0.3%": {
        "address": "0x4e68Ccd3E89f51C3074ca5072bbAC773960dFa36",
        "token0": "WETH",
        "token1": "USDT",
        "decimals0": 18,
        "decimals1": 6,
    },
    "ETH-USDT-0.05%": {
        "address": "0xc5aF84701f98Fa483eCe78aF83F11b6C38ACA71D",
        "token0": "WETH",
        "token1": "USDT",
        "decimals0": 18,
        "decimals1": 6,
    },
    "ETH-DAI-0.3%": {
        "address": "0xC2e9F25Be6257c210d7Adf0D4Cd6E3E881ba25f8",
        "token0": "WETH",
        "token1": "DAI",
        "decimals0": 18,
        "decimals1": 18,
    },
}

# Backward compatibility
UNISWAP_V3_ETH_USDC_POOL = UNISWAP_V3_POOLS["ETH-USDC-0.3%"]["address"]

# Uniswap V3 Router (where most swaps go through)
UNISWAP_V3_ROUTER = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
UNISWAP_V3_SWAP_ROUTER_02 = "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45"

# Uniswap V3 Pool ABI (Swap event only)
UNISWAP_V3_POOL_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "sender", "type": "address"},
            {"indexed": True, "name": "recipient", "type": "address"},
            {"indexed": False, "name": "amount0", "type": "int256"},
            {"indexed": False, "name": "amount1", "type": "int256"},
            {"indexed": False, "name": "sqrtPriceX96", "type": "uint160"},
            {"indexed": False, "name": "liquidity", "type": "uint128"},
            {"indexed": False, "name": "tick", "type": "int24"}
        ],
        "name": "Swap",
        "type": "event"
    },
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"name": "sqrtPriceX96", "type": "uint160"},
            {"name": "tick", "type": "int24"},
            {"name": "observationIndex", "type": "uint16"},
            {"name": "observationCardinality", "type": "uint16"},
            {"name": "observationCardinalityNext", "type": "uint16"},
            {"name": "feeProtocol", "type": "uint8"},
            {"name": "unlocked", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]


class DEXPriceFeed:
    """
    Real-time DEX price feed monitoring Uniswap v3 swaps.

    Uses Alchemy's WebSocket API to listen for on-chain swap events.
    Completely decentralized - reads directly from blockchain.

    Free tier: 300M compute units/month (plenty for 24/7 monitoring)
    """

    def __init__(self, alchemy_api_key: Optional[str] = None, pools: list[str] = None):
        """
        Initialize DEX price feed.

        Args:
            alchemy_api_key: Alchemy API key (or set ALCHEMY_API_KEY in .env)
            pools: List of pool names to monitor (e.g., ["ETH-USDC-0.3%", "ETH-USDT-0.3%"])
                   If None, monitors all major ETH pools
        """
        self.api_key = alchemy_api_key or os.getenv("ALCHEMY_API_KEY")

        if not self.api_key:
            # Fallback to free public RPC
            logger.warning("No Alchemy API key found, using free PublicNode RPC")
            self.wss_url = "wss://ethereum-rpc.publicnode.com"
        else:
            # Alchemy WebSocket URL format (v2)
            self.wss_url = f"wss://eth-mainnet.g.alchemy.com/v2/{self.api_key}"

        # Select pools to monitor (all major ETH pools by default)
        self.pools_to_monitor = pools or list(UNISWAP_V3_POOLS.keys())
        self.pool_configs = {name: UNISWAP_V3_POOLS[name] for name in self.pools_to_monitor}

        self.w3: Optional[AsyncWeb3] = None
        self.pool_contracts = {}  # Store contracts for each pool
        self.current_prices = {}  # Store current price for each pool
        self.price_callbacks: list[Callable] = []
        self.swap_count = 0
        self.pending_swap_count = 0

    def _calculate_price_from_sqrt(self, sqrt_price_x96: int, pool_config: Dict) -> Decimal:
        """
        Calculate ETH price in USD from Uniswap's sqrtPriceX96.

        Formula: price = (sqrtPriceX96 / 2^96)^2

        The sqrtPriceX96 represents sqrt(token1/token0) in the pool.
        We need to handle different token orderings to always return USD per ETH.

        Args:
            sqrt_price_x96: Square root of price in X96 format
            pool_config: Pool configuration with token ordering and decimals

        Returns:
            ETH price in USD
        """
        # Convert from X96 format
        sqrt_price = Decimal(sqrt_price_x96) / Decimal(2 ** 96)

        # Square to get the ratio: token1/token0
        price_ratio = sqrt_price ** 2

        # Get token info
        token0 = pool_config['token0']
        token1 = pool_config['token1']
        decimals0 = pool_config['decimals0']
        decimals1 = pool_config['decimals1']

        # Adjust for decimals difference
        # price_ratio * 10^(decimals0 - decimals1)
        decimal_adjustment = Decimal(10 ** (decimals0 - decimals1))
        adjusted_price = price_ratio * decimal_adjustment

        # Now determine what this price represents and convert to USD per ETH
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
        logger.info(f"Connecting to Ethereum via Alchemy WebSocket...")

        # Connect to WebSocket using async context manager
        # Note: We'll use __aenter__ manually to keep connection open
        provider = WebSocketProvider(self.wss_url)
        self.w3 = AsyncWeb3(provider)

        # Manually await connection
        await self.w3.provider.connect()

        # Verify connection
        is_connected = await self.w3.is_connected()
        if not is_connected:
            raise ConnectionError("Failed to connect to Ethereum WebSocket")

        logger.info("✓ Connected to Ethereum mainnet")

        # Setup Uniswap V3 pool contract
        self.pool_contract = self.w3.eth.contract(
            address=UNISWAP_V3_ETH_USDC_POOL,
            abi=UNISWAP_V3_POOL_ABI
        )

        # Get initial price
        await self._update_current_price()

    async def _update_current_price(self):
        """Fetch current price from pool's slot0."""
        try:
            # Call slot0() to get current pool state
            slot0 = await self.pool_contract.functions.slot0().call()
            sqrt_price_x96 = slot0[0]

            # Calculate price using ETH-USDC-0.3% pool config
            pool_config = UNISWAP_V3_POOLS["ETH-USDC-0.3%"]
            self.current_price = self._calculate_price_from_sqrt(sqrt_price_x96, pool_config)

            logger.info(f"📊 Current Uniswap V3 ETH/USDC: ${self.current_price:.2f}")

        except Exception as e:
            logger.error(f"Error fetching current price: {e}")

    async def _handle_swap_log(self, log_receipt):
        """Process a single swap log event."""
        try:
            self.swap_count += 1

            # Identify which pool this swap is from
            # Handle both string and bytes addresses
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

            # Determine which amount is ETH/WETH based on pool config
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

            # Prepare price data
            price_data = {
                'price': new_price,
                'eth_amount': Decimal(str(eth_amount)),
                'stablecoin_amount': Decimal(str(stablecoin_amount)),
                'stablecoin': stablecoin,
                'trade_value_usd': Decimal(str(trade_value_usd)),
                'direction': direction,
                'exchange': 'UNISWAP_V3',
                'pool': pool_name,
                'timestamp': datetime.now(),
                'tx_hash': tx_hash_hex
            }

            # Notify callbacks
            await self._notify_callbacks(price_data)

        except Exception as e:
            logger.error(f"Error processing swap event: {e}")

    async def _handle_pending_swap(self, tx_hash: str):
        """Process a pending swap transaction from mempool."""
        try:
            self.pending_swap_count += 1

            # Fetch pending transaction details
            tx = await self.w3.eth.get_transaction(tx_hash)

            if not tx or not tx.get('input'):
                return

            # Check if transaction is to Uniswap pool
            if tx.get('to') and tx['to'].lower() != UNISWAP_V3_ETH_USDC_POOL.lower():
                return

            # Get transaction value
            value_wei = tx.get('value', 0)
            value_eth = float(value_wei) / 10**18 if value_wei else 0

            # Estimate USD value using current price
            if self.current_price and value_eth > 0:
                estimated_usd = value_eth * float(self.current_price)
                logger.info(
                    f"⏳ Pending Swap #{self.pending_swap_count} | "
                    f"ETH: {value_eth:.4f} (~${estimated_usd:,.2f}) | "
                    f"TX: {tx_hash[:16]}... | "
                    f"Gas: {tx.get('gasPrice', 0) / 10**9:.2f} Gwei"
                )
            else:
                logger.info(
                    f"⏳ Pending Swap #{self.pending_swap_count} | TX: {tx_hash[:16]}..."
                )

        except Exception as e:
            logger.debug(f"Error processing pending swap: {e}")

    async def subscribe_to_pending_swaps(self):
        """Subscribe to pending Uniswap V3 swaps using Alchemy's alchemy_pendingTransactions."""
        logger.info("Subscribing to pending Uniswap V3 swaps (mempool)...")

        # Monitor both the pool directly and the routers (where most swaps happen)
        pool_address = self.w3.to_checksum_address(UNISWAP_V3_ETH_USDC_POOL)
        router_address = self.w3.to_checksum_address(UNISWAP_V3_ROUTER)
        router2_address = self.w3.to_checksum_address(UNISWAP_V3_SWAP_ROUTER_02)

        # Alchemy's pending transaction filter - monitor routers for more activity
        filter_params = {
            "toAddress": [router_address, router2_address, pool_address],
            "hashesOnly": True  # Get only hashes for efficiency
        }

        try:
            # Subscribe to Alchemy's pending transactions
            subscription_id = await self.w3.eth.subscribe("alchemy_pendingTransactions", filter_params)
            logger.info(f"✓ Subscribed to pending swaps (mempool) (ID: {subscription_id})")

            # Listen for pending transactions
            async for payload in self.w3.socket.process_subscriptions():
                try:
                    if isinstance(payload.get("result"), str):
                        # It's a transaction hash
                        tx_hash = payload["result"]
                        await self._handle_pending_swap(tx_hash)
                    elif isinstance(payload.get("result"), dict):
                        # It's a full transaction object
                        tx_hash = payload["result"].get("hash")
                        if tx_hash:
                            await self._handle_pending_swap(tx_hash)

                except Exception as e:
                    logger.debug(f"Error processing pending tx: {e}")

        except Exception as e:
            logger.warning(f"Pending transactions subscription failed: {e}")
            logger.info("Mempool monitoring requires Alchemy Growth tier or higher")

    async def subscribe_to_swaps(self):
        """Subscribe to Uniswap V3 swap events for all monitored pools."""
        logger.info(f"Subscribing to {len(self.pool_configs)} Uniswap V3 pools...")

        # Get Swap event topic (ensure it has 0x prefix)
        swap_event_topic = self.w3.keccak(text="Swap(address,address,int256,int256,uint160,uint128,int24)").hex()
        if not swap_event_topic.startswith('0x'):
            swap_event_topic = '0x' + swap_event_topic

        # Get all pool addresses to monitor
        pool_addresses = [
            self.w3.to_checksum_address(config["address"])
            for config in self.pool_configs.values()
        ]

        # Create filter params to monitor ALL pools at once
        filter_params = {
            "address": pool_addresses,  # Multiple addresses
            "topics": [swap_event_topic]
        }

        logger.info(f"Monitoring pools: {', '.join(self.pools_to_monitor)}")

        # Try subscribing with web3.py
        try:
            subscription_id = await self.w3.eth.subscribe("logs", filter_params)
            logger.info(f"✓ Subscribed to real-time DEX swaps (ID: {subscription_id})")
        except Exception as e:
            logger.error(f"Subscription failed: {e}")
            logger.info("This appears to be an Alchemy WebSocket limitation.")
            logger.info("Consider using HTTP polling or Alchemy Notify webhooks instead.")
            raise

        logger.info(f"✓ Monitoring {len(pool_addresses)} Uniswap V3 pools")

        # Listen for swap events
        async for payload in self.w3.socket.process_subscriptions():
            try:
                result = payload["result"]
                await self._handle_swap_log(result)

            except Exception as e:
                logger.error(f"Error receiving swap event: {e}")
                break

    async def _notify_callbacks(self, price_data: Dict):
        """Notify all registered callbacks of price update."""
        for callback in self.price_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(price_data)
                else:
                    callback(price_data)
            except Exception as e:
                logger.error(f"Error in price callback: {e}")

    def on_price_update(self, callback: Callable):
        """
        Register callback for DEX price updates.

        Args:
            callback: Function(price_data) - called on each Uniswap swap

        Example:
            async def my_strategy(data):
                print(f"DEX Price: ${data['price']}")

            feed.on_price_update(my_strategy)
        """
        self.price_callbacks.append(callback)

    async def get_current_price(self) -> Optional[Decimal]:
        """Get current cached DEX price."""
        return self.current_price

    async def start(self, enable_mempool: bool = True):
        """
        Start DEX price feed.

        Args:
            enable_mempool: If True, also subscribe to pending transactions (mempool)
        """
        await self.connect()

        # Run both confirmed swaps and pending swaps concurrently
        if enable_mempool:
            await asyncio.gather(
                self.subscribe_to_swaps(),
                self.subscribe_to_pending_swaps(),
                return_exceptions=True
            )
        else:
            await self.subscribe_to_swaps()

    async def stop(self):
        """Stop DEX price feed."""
        if self.w3 and hasattr(self.w3.provider, 'disconnect'):
            await self.w3.provider.disconnect()
        logger.info("DEX price feed stopped")


# Example usage
async def main():
    """Example: Monitor Uniswap V3 ETH/USDC swaps in real-time."""

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Create DEX feed
    feed = DEXPriceFeed()

    # Define trading strategy
    async def dex_arbitrage_strategy(data):
        """
        Example: DEX arbitrage monitoring.

        Compare DEX price with CEX prices to find arbitrage opportunities.
        """
        dex_price = data['price']
        exchange = data['exchange']

        print(f"\n💎 {exchange} {data['pool']}: ${dex_price:.2f}")
        print(f"   Direction: {data['direction']}")
        print(f"   Volume: {data['eth_amount']:.4f} ETH")
        print(f"   TX: {data['tx_hash'][:16]}...")

        # Example: Compare with CEX price (you'd get this from CryptoFeed)
        # cex_price = get_binance_price()
        # if abs(dex_price - cex_price) > 10:  # $10 difference
        #     print(f"🚨 ARBITRAGE OPPORTUNITY!")
        #     print(f"   DEX: ${dex_price:.2f}")
        #     print(f"   CEX: ${cex_price:.2f}")
        #     print(f"   Profit: ${abs(dex_price - cex_price):.2f}")

    # Register callback
    feed.on_price_update(dex_arbitrage_strategy)

    # Start feed
    try:
        await feed.start()
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        await feed.stop()


if __name__ == "__main__":
    asyncio.run(main())
