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
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# Uniswap V3 ETH/USDC Pool (0.3% fee tier)
UNISWAP_V3_ETH_USDC_POOL = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"

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

    def __init__(self, alchemy_api_key: Optional[str] = None):
        """
        Initialize DEX price feed.

        Args:
            alchemy_api_key: Alchemy API key (or set ALCHEMY_API_KEY in .env)
        """
        self.api_key = alchemy_api_key or os.getenv("ALCHEMY_API_KEY")

        if not self.api_key:
            # Fallback to free public RPC
            logger.warning("No Alchemy API key found, using free PublicNode RPC")
            self.wss_url = "wss://ethereum-rpc.publicnode.com"
        else:
            # Alchemy WebSocket URL format (v2)
            self.wss_url = f"wss://eth-mainnet.g.alchemy.com/v2/{self.api_key}"

        self.w3: Optional[AsyncWeb3] = None
        self.pool_contract = None
        self.current_price: Optional[Decimal] = None
        self.price_callbacks: list[Callable] = []
        self.swap_count = 0

    def _calculate_price_from_sqrt(self, sqrt_price_x96: int) -> Decimal:
        """
        Calculate ETH/USDC price from Uniswap's sqrtPriceX96.

        Formula: price = (sqrtPriceX96 / 2^96)^2 * 10^(decimals0 - decimals1)
        For ETH/USDC: decimals0=18 (ETH), decimals1=6 (USDC)

        Args:
            sqrt_price_x96: Square root of price in X96 format

        Returns:
            ETH price in USDC
        """
        # Convert from X96 format
        sqrt_price = Decimal(sqrt_price_x96) / Decimal(2 ** 96)

        # Square to get the actual price
        price = sqrt_price ** 2

        # Adjust for decimals (ETH has 18, USDC has 6)
        # Price is USDC per ETH, so we need to multiply by 10^12
        price = price * Decimal(10 ** 12)

        return price

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

            # Calculate price
            self.current_price = self._calculate_price_from_sqrt(sqrt_price_x96)

            logger.info(f"📊 Current Uniswap V3 ETH/USDC: ${self.current_price:.2f}")

        except Exception as e:
            logger.error(f"Error fetching current price: {e}")

    async def subscribe_to_swaps(self):
        """Subscribe to Uniswap V3 swap events in real-time."""
        logger.info("Subscribing to Uniswap V3 swaps...")

        # Get Swap event topic
        swap_event_topic = self.w3.keccak(text="Swap(address,address,int256,int256,uint160,uint128,int24)").hex()

        # Subscribe to logs for the Uniswap pool (checksum address required)
        checksum_address = self.w3.to_checksum_address(UNISWAP_V3_ETH_USDC_POOL)
        filter_params = {
            "address": checksum_address,
            "topics": [swap_event_topic],
        }

        subscription_id = await self.w3.eth.subscribe("logs", filter_params)

        logger.info("✓ Subscribed to real-time DEX swaps")
        logger.info("✓ Monitoring Uniswap V3 ETH/USDC pool")

        # Listen for swap events
        async for payload in self.w3.socket.process_subscriptions():
            try:
                result = payload["result"]
                self.swap_count += 1

                # Decode event data
                log_receipt = self.pool_contract.events.Swap().process_log(result)

                # Extract swap data
                sqrt_price_x96 = log_receipt['args']['sqrtPriceX96']
                amount0 = log_receipt['args']['amount0']  # ETH amount
                amount1 = log_receipt['args']['amount1']  # USDC amount

                # Calculate new price
                new_price = self._calculate_price_from_sqrt(sqrt_price_x96)
                self.current_price = new_price

                # Determine trade direction
                if amount0 < 0:  # ETH sold (bought USDC)
                    direction = "SELL"
                    eth_amount = abs(amount0) / 10**18
                    usdc_amount = abs(amount1) / 10**6
                else:  # ETH bought (sold USDC)
                    direction = "BUY"
                    eth_amount = amount0 / 10**18
                    usdc_amount = abs(amount1) / 10**6

                logger.info(
                    f"🔄 Uniswap V3 Swap #{self.swap_count} - "
                    f"${new_price:.2f} ({direction}) "
                    f"ETH: {eth_amount:.4f} USDC: {usdc_amount:.2f}"
                )

                # Prepare price data
                price_data = {
                    'price': new_price,
                    'eth_amount': Decimal(str(eth_amount)),
                    'usdc_amount': Decimal(str(usdc_amount)),
                    'direction': direction,
                    'exchange': 'UNISWAP_V3',
                    'pair': 'ETH-USDC',
                    'timestamp': datetime.now(),
                    'tx_hash': result['transactionHash'].hex()
                }

                # Notify callbacks
                await self._notify_callbacks(price_data)

            except Exception as e:
                logger.error(f"Error processing swap event: {e}")

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

    async def start(self):
        """Start DEX price feed."""
        await self.connect()
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

        print(f"\n💎 {exchange} {data['pair']}: ${dex_price:.2f}")
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
