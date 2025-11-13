"""
SushiSwap real-time stream handler.

Monitors SushiSwap (Uniswap V2 fork) pairs on Ethereum for real-time swap events.
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

from config.loader import get_sushiswap_config

load_dotenv()

logger = logging.getLogger(__name__)

# Load SushiSwap configuration
_sushiswap_config = get_sushiswap_config()
SUSHISWAP_PAIRS = _sushiswap_config['pairs']
SUSHISWAP_ROUTER = _sushiswap_config['router']
SUSHISWAP_FACTORY = _sushiswap_config['factory']

# SushiSwap Pair ABI (Uniswap V2 compatible - Swap event)
SUSHISWAP_PAIR_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "sender", "type": "address"},
            {"indexed": False, "name": "amount0In", "type": "uint256"},
            {"indexed": False, "name": "amount1In", "type": "uint256"},
            {"indexed": False, "name": "amount0Out", "type": "uint256"},
            {"indexed": False, "name": "amount1Out", "type": "uint256"},
            {"indexed": True, "name": "to", "type": "address"}
        ],
        "name": "Swap",
        "type": "event"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {"name": "_reserve0", "type": "uint112"},
            {"name": "_reserve1", "type": "uint112"},
            {"name": "_blockTimestampLast", "type": "uint32"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]


class SushiSwapStream:
    """
    Real-time SushiSwap stream handler.

    Monitors SushiSwap pairs for swap events. SushiSwap is a Uniswap V2 fork
    with constant product AMM (x * y = k).

    Architecture fit:
    - Part of market_data/stream layer
    - Emits events to event bus (to be integrated)
    - Provides data for analytics engine

    Usage:
        stream = SushiSwapStream(pairs=["ETH-USDC", "ETH-USDT"])
        stream.on_swap(callback_function)
        await stream.start()
    """

    def __init__(
        self,
        alchemy_api_key: Optional[str] = None,
        pairs: Optional[List[str]] = None,
        chain: str = "ethereum"
    ):
        """
        Initialize SushiSwap stream.

        Args:
            alchemy_api_key: Alchemy API key (or set ALCHEMY_API_KEY in .env)
            pairs: List of pair names to monitor (default: all major ETH pairs)
            chain: Blockchain network (currently only "ethereum" supported)
        """
        self.api_key = alchemy_api_key or os.getenv("ALCHEMY_API_KEY")
        self.chain = chain

        if not self.api_key:
            raise ValueError("Alchemy API key required. Set ALCHEMY_API_KEY in .env")

        self.wss_url = f"wss://eth-mainnet.g.alchemy.com/v2/{self.api_key}"

        # Select pairs to monitor
        self.pairs_to_monitor = pairs or list(SUSHISWAP_PAIRS.keys())
        self.pair_configs = {
            name: SUSHISWAP_PAIRS[name]
            for name in self.pairs_to_monitor
        }

        self.w3: Optional[AsyncWeb3] = None
        self.pair_contracts = {}
        self.current_prices = {}
        self.swap_callbacks: List[Callable] = []
        self.swap_count = 0
        self._running = False

    def _calculate_price(self, pair_config: Dict, amount0In: int, amount1In: int,
                        amount0Out: int, amount1Out: int) -> Decimal:
        """
        Calculate ETH price in USD from SushiSwap swap.

        SushiSwap uses constant product AMM (Uniswap V2).
        We derive price from the swap amounts.

        Args:
            pair_config: Pair configuration
            amount0In: Amount of token0 swapped in
            amount1In: Amount of token1 swapped in
            amount0Out: Amount of token0 swapped out
            amount1Out: Amount of token1 swapped out

        Returns:
            ETH price in USD, or None if swap doesn't involve meaningful ETH amounts
        """
        token0 = pair_config['token0']
        token1 = pair_config['token1']
        decimals0 = pair_config['decimals0']
        decimals1 = pair_config['decimals1']

        # Adjust for decimals
        amount0_in_adjusted = Decimal(amount0In) / Decimal(10 ** decimals0)
        amount1_in_adjusted = Decimal(amount1In) / Decimal(10 ** decimals1)
        amount0_out_adjusted = Decimal(amount0Out) / Decimal(10 ** decimals0)
        amount1_out_adjusted = Decimal(amount1Out) / Decimal(10 ** decimals1)

        # Calculate effective amounts (net flow)
        net_amount0 = amount0_out_adjusted - amount0_in_adjusted
        net_amount1 = amount1_out_adjusted - amount1_in_adjusted

        # Determine which is ETH and which is stablecoin
        if 'WETH' in token0 or 'ETH' in token0:
            # token0 is WETH, token1 is stablecoin
            eth_amount = abs(net_amount0)
            stablecoin_amount = abs(net_amount1)
        else:
            # token1 is WETH, token0 is stablecoin
            eth_amount = abs(net_amount1)
            stablecoin_amount = abs(net_amount0)

        # Minimum ETH threshold: 0.0001 ETH (~$0.30 at current prices)
        # This filters out dust/rounding errors that produce invalid prices
        MIN_ETH_THRESHOLD = Decimal('0.0001')

        # Calculate price (USD per ETH)
        if eth_amount >= MIN_ETH_THRESHOLD:
            price = stablecoin_amount / eth_amount
        else:
            # Skip swaps with negligible ETH amounts - they produce invalid prices
            price = None

        return price

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

            logger.info("✓ Connected to Ethereum mainnet (SushiSwap)")

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

            # Identify which pair this swap is from
            raw_address = log_receipt['address']
            if isinstance(raw_address, bytes):
                pair_address = '0x' + raw_address.hex().lower()
            else:
                pair_address = raw_address.lower()

            if not pair_address.startswith('0x'):
                pair_address = '0x' + pair_address

            pair_name = None
            pair_config = None

            for name, config in self.pair_configs.items():
                if config['address'].lower() == pair_address:
                    pair_name = name
                    pair_config = config
                    break

            if not pair_config:
                logger.debug(f"Ignoring swap from unknown pair: {pair_address}")
                return

            # Get pair contract (create if not exists)
            if pair_address not in self.pair_contracts:
                checksum_address = self.w3.to_checksum_address(pair_address)
                self.pair_contracts[pair_address] = self.w3.eth.contract(
                    address=checksum_address,
                    abi=SUSHISWAP_PAIR_ABI
                )

            # Decode event data
            decoded_log = self.pair_contracts[pair_address].events.Swap().process_log(log_receipt)

            # Extract swap data
            amount0In = decoded_log['args']['amount0In']
            amount1In = decoded_log['args']['amount1In']
            amount0Out = decoded_log['args']['amount0Out']
            amount1Out = decoded_log['args']['amount1Out']

            # Get token info
            token0 = pair_config['token0']
            token1 = pair_config['token1']
            decimals0 = pair_config['decimals0']
            decimals1 = pair_config['decimals1']

            # Calculate amounts
            amount0_in_adjusted = Decimal(amount0In) / Decimal(10 ** decimals0)
            amount1_in_adjusted = Decimal(amount1In) / Decimal(10 ** decimals1)
            amount0_out_adjusted = Decimal(amount0Out) / Decimal(10 ** decimals0)
            amount1_out_adjusted = Decimal(amount1Out) / Decimal(10 ** decimals1)

            # Calculate price
            price = self._calculate_price(
                pair_config, amount0In, amount1In, amount0Out, amount1Out
            )

            # Skip swaps with invalid/negligible ETH amounts
            if price is None:
                logger.debug(
                    f"Skipping SushiSwap swap with negligible ETH amount "
                    f"(would produce invalid price) - Pair: {pair_name}"
                )
                return

            if price > 0:
                self.current_prices[pair_name] = price

            # Determine direction and amounts
            if 'WETH' in token0 or 'ETH' in token0:
                # token0 is WETH
                if amount0In > 0:
                    direction = "SELL"
                    eth_amount = amount0_in_adjusted
                    stablecoin_amount = amount1_out_adjusted
                else:
                    direction = "BUY"
                    eth_amount = amount0_out_adjusted
                    stablecoin_amount = amount1_in_adjusted
                stablecoin = token1
            else:
                # token1 is WETH
                if amount1In > 0:
                    direction = "SELL"
                    eth_amount = amount1_in_adjusted
                    stablecoin_amount = amount0_out_adjusted
                else:
                    direction = "BUY"
                    eth_amount = amount1_out_adjusted
                    stablecoin_amount = amount0_in_adjusted
                stablecoin = token0

            # Calculate USD value
            trade_value_usd = eth_amount * price if price > 0 else Decimal(0)

            # Handle transaction hash
            tx_hash = log_receipt['transactionHash']
            if isinstance(tx_hash, bytes):
                tx_hash_hex = '0x' + tx_hash.hex()
            elif isinstance(tx_hash, str):
                tx_hash_hex = tx_hash if tx_hash.startswith('0x') else '0x' + tx_hash
            else:
                tx_hash_hex = str(tx_hash)

            logger.info(
                f"🔄 SushiSwap Swap #{self.swap_count} [{pair_name}] | {direction} | "
                f"ETH: {eth_amount:.4f} (${trade_value_usd:,.2f}) | "
                f"{stablecoin}: {stablecoin_amount:,.2f} | "
                f"Price: ${price:,.2f}"
            )

            # Prepare swap data
            swap_data = {
                'price': price,
                'eth_amount': eth_amount,
                'stablecoin_amount': stablecoin_amount,
                'stablecoin': stablecoin,
                'trade_value_usd': trade_value_usd,
                'direction': direction,
                'exchange': 'SUSHISWAP',
                'pool': pair_name,
                'timestamp': datetime.now(),
                'tx_hash': tx_hash_hex
            }

            # Notify callbacks
            await self._notify_callbacks(swap_data)

        except Exception as e:
            logger.error(f"Error processing SushiSwap swap event: {e}")

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
        """Start monitoring SushiSwap pairs."""
        if self._running:
            logger.warning("SushiSwap stream already running")
            return

        self._running = True

        # Connect to Ethereum
        await self.connect()

        # Get all pair addresses
        pair_addresses = [
            self.w3.to_checksum_address(config['address'])
            for config in self.pair_configs.values()
        ]

        logger.info(f"Starting SushiSwap stream for {len(pair_addresses)} pairs...")
        logger.info(f"Monitoring: {', '.join(self.pairs_to_monitor)}")

        # Subscribe to Swap events from all pairs
        try:
            # Get Swap event topic (Uniswap V2 compatible)
            swap_event_topic = self.w3.keccak(
                text='Swap(address,uint256,uint256,uint256,uint256,address)'
            ).hex()
            if not swap_event_topic.startswith('0x'):
                swap_event_topic = '0x' + swap_event_topic

            # Create filter params for WebSocket subscription
            filter_params = {
                'address': pair_addresses,
                'topics': [swap_event_topic]
            }

            # Subscribe using WebSocket
            subscription_id = await self.w3.eth.subscribe("logs", filter_params)
            logger.info(f"✓ Subscribed to SushiSwap Swap events (ID: {subscription_id})")
            logger.info(f"✓ Monitoring {len(pair_addresses)} SushiSwap pairs")

            # Stream events in real-time
            async for payload in self.w3.socket.process_subscriptions():
                if not self._running:
                    break

                try:
                    result = payload["result"]
                    await self._handle_swap_log(result)
                except Exception as e:
                    logger.error(f"Error receiving SushiSwap swap event: {e}")

        except Exception as e:
            logger.error(f"Failed to subscribe to SushiSwap events: {e}")
            raise

    async def stop(self):
        """Stop monitoring SushiSwap pairs."""
        self._running = False

        if self.w3 and self.w3.provider:
            await self.w3.provider.disconnect()

        logger.info("SushiSwap stream stopped")

    def get_current_prices(self) -> Dict[str, Decimal]:
        """
        Get current prices from all monitored pairs.

        Returns:
            Dictionary mapping pair names to current prices
        """
        return self.current_prices.copy()
