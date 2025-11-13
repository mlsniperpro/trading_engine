"""
Market Data Manager - Central coordinator for all market data streams.

Manages multiple data streams (DEX + CEX) and provides unified interface.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Callable
from decimal import Decimal

from .dex_stream import DEXStream
from .cex_stream import CEXStream

logger = logging.getLogger(__name__)


class MarketDataManager:
    """
    Central coordinator for market data streams.

    Manages both DEX and CEX streams, provides arbitrage detection,
    and emits unified market data events.

    Architecture fit:
    - Part of market_data/stream layer
    - Coordinates multiple data sources
    - Future: Will emit events to core/event_bus.py
    - Future: Will store data via storage/database_manager.py

    Usage:
        manager = MarketDataManager(
            enable_dex=True,
            enable_cex=True,
            dex_pools=["ETH-USDC-0.3%"],
            cex_symbols=["ETH-USDT"]
        )
        manager.on_arbitrage(callback)
        await manager.start()
    """

    def __init__(
        self,
        enable_dex: bool = True,
        enable_cex: bool = True,
        dex_pools: Optional[List[str]] = None,
        cex_symbols: Optional[List[str]] = None,
        arbitrage_threshold_pct: float = 0.5,  # 0.5% price difference
    ):
        """
        Initialize MarketDataManager.

        Args:
            enable_dex: Enable DEX stream (Uniswap)
            enable_cex: Enable CEX stream (Binance)
            dex_pools: List of DEX pools to monitor
            cex_symbols: List of CEX symbols to monitor
            arbitrage_threshold_pct: Minimum price difference % for arbitrage alert
        """
        self.enable_dex = enable_dex
        self.enable_cex = enable_cex
        self.arbitrage_threshold = Decimal(str(arbitrage_threshold_pct / 100))

        # Initialize streams
        self.dex_stream = DEXStream(pools=dex_pools) if enable_dex else None
        self.cex_stream = CEXStream(symbols=cex_symbols) if enable_cex else None

        # Price tracking
        self.dex_prices: Dict[str, Decimal] = {}  # pool_name -> price
        self.cex_prices: Dict[str, Decimal] = {}  # symbol -> price

        # Callbacks
        self.arbitrage_callbacks: List[Callable] = []
        self.unified_price_callbacks: List[Callable] = []

        self._running = False

    async def _handle_dex_swap(self, swap_data: Dict):
        """Handle DEX swap event."""
        try:
            pool = swap_data['pool']
            price = swap_data['price']

            # Update DEX price
            self.dex_prices[pool] = price

            # Check for arbitrage opportunities
            await self._check_arbitrage(source='DEX', pool=pool, price=price)

            # Emit unified price event
            await self._emit_unified_price({
                'source': 'DEX',
                'venue': 'UNISWAP_V3',
                'pair': pool,
                'price': price,
                'timestamp': swap_data['timestamp'],
                'volume': swap_data['trade_value_usd'],
            })

        except Exception as e:
            logger.error(f"Error handling DEX swap: {e}")

    async def _handle_cex_trade(self, trade_data: Dict):
        """Handle CEX trade event."""
        try:
            symbol = trade_data['symbol']
            price = trade_data['price']

            # Update CEX price
            self.cex_prices[symbol] = price

            # Check for arbitrage opportunities
            await self._check_arbitrage(source='CEX', symbol=symbol, price=price)

            # Emit unified price event
            await self._emit_unified_price({
                'source': 'CEX',
                'venue': trade_data['exchange'],
                'pair': symbol,
                'price': price,
                'timestamp': trade_data['timestamp'],
                'volume': trade_data['price'] * trade_data['amount'],
            })

        except Exception as e:
            logger.error(f"Error handling CEX trade: {e}")

    async def _check_arbitrage(
        self,
        source: str,
        price: Decimal,
        pool: Optional[str] = None,
        symbol: Optional[str] = None
    ):
        """
        Check for arbitrage opportunities between DEX and CEX.

        Args:
            source: 'DEX' or 'CEX'
            price: Current price
            pool: DEX pool name (if source='DEX')
            symbol: CEX symbol (if source='CEX')
        """
        try:
            # Only check ETH pairs for now
            if source == 'DEX' and pool and 'ETH-USDC' in pool:
                # Compare with Binance ETH-USDT
                cex_price = self.cex_prices.get('ETH-USDT')
                if cex_price:
                    dex_price = price
                    price_diff = abs(dex_price - cex_price)
                    price_diff_pct = (price_diff / cex_price) * 100

                    if price_diff_pct >= (self.arbitrage_threshold * 100):
                        arbitrage_data = {
                            'dex_price': dex_price,
                            'cex_price': cex_price,
                            'dex_pool': pool,
                            'cex_symbol': 'ETH-USDT',
                            'price_diff': price_diff,
                            'price_diff_pct': price_diff_pct,
                            'direction': 'BUY_CEX_SELL_DEX' if cex_price < dex_price else 'BUY_DEX_SELL_CEX',
                        }

                        logger.warning(
                            f"🚨 ARBITRAGE OPPORTUNITY! | "
                            f"DEX: ${dex_price:.2f} | CEX: ${cex_price:.2f} | "
                            f"Diff: {price_diff_pct:.2f}% | "
                            f"Action: {arbitrage_data['direction']}"
                        )

                        await self._notify_arbitrage_callbacks(arbitrage_data)

            elif source == 'CEX' and symbol == 'ETH-USDT':
                # Compare with all ETH-USDC DEX pools
                for pool_name, dex_price in self.dex_prices.items():
                    if 'ETH-USDC' in pool_name:
                        cex_price = price
                        price_diff = abs(dex_price - cex_price)
                        price_diff_pct = (price_diff / cex_price) * 100

                        if price_diff_pct >= (self.arbitrage_threshold * 100):
                            arbitrage_data = {
                                'dex_price': dex_price,
                                'cex_price': cex_price,
                                'dex_pool': pool_name,
                                'cex_symbol': symbol,
                                'price_diff': price_diff,
                                'price_diff_pct': price_diff_pct,
                                'direction': 'BUY_CEX_SELL_DEX' if cex_price < dex_price else 'BUY_DEX_SELL_CEX',
                            }

                            logger.warning(
                                f"🚨 ARBITRAGE OPPORTUNITY! | "
                                f"DEX: ${dex_price:.2f} | CEX: ${cex_price:.2f} | "
                                f"Diff: {price_diff_pct:.2f}% | "
                                f"Action: {arbitrage_data['direction']}"
                            )

                            await self._notify_arbitrage_callbacks(arbitrage_data)
                            break  # Only report once per CEX update

        except Exception as e:
            logger.error(f"Error checking arbitrage: {e}")

    async def _emit_unified_price(self, price_data: Dict):
        """Emit unified price event to callbacks."""
        for callback in self.unified_price_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(price_data)
                else:
                    callback(price_data)
            except Exception as e:
                logger.error(f"Error in unified price callback: {e}")

    async def _notify_arbitrage_callbacks(self, arbitrage_data: Dict):
        """Notify all registered arbitrage callbacks."""
        for callback in self.arbitrage_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(arbitrage_data)
                else:
                    callback(arbitrage_data)
            except Exception as e:
                logger.error(f"Error in arbitrage callback: {e}")

    def on_arbitrage(self, callback: Callable):
        """
        Register callback for arbitrage opportunities.

        Args:
            callback: Function(arbitrage_data) - called when arbitrage detected
        """
        self.arbitrage_callbacks.append(callback)

    def on_price(self, callback: Callable):
        """
        Register callback for unified price updates.

        Args:
            callback: Function(price_data) - called on each price update
        """
        self.unified_price_callbacks.append(callback)

    async def start(self):
        """Start all enabled streams."""
        self._running = True

        logger.info("=" * 60)
        logger.info("🚀 Starting Market Data Manager")
        logger.info("=" * 60)

        tasks = []

        # Start DEX stream
        if self.enable_dex and self.dex_stream:
            self.dex_stream.on_swap(self._handle_dex_swap)
            tasks.append(self.dex_stream.start())
            logger.info("✓ DEX stream enabled")

        # Start CEX stream
        if self.enable_cex and self.cex_stream:
            self.cex_stream.on_trade(self._handle_cex_trade)
            tasks.append(self.cex_stream.start())
            logger.info("✓ CEX stream enabled")

        if not tasks:
            logger.error("No streams enabled!")
            return

        logger.info("=" * 60)
        logger.info(f"Arbitrage threshold: {self.arbitrage_threshold * 100}%")
        logger.info("=" * 60)

        # Run all streams concurrently
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error in market data manager: {e}")
            raise

    async def stop(self):
        """Stop all streams."""
        self._running = False

        if self.dex_stream:
            await self.dex_stream.stop()

        if self.cex_stream:
            await self.cex_stream.stop()

        logger.info("Market Data Manager stopped")

    def get_current_prices(self) -> Dict:
        """
        Get current prices from all sources.

        Returns:
            Dict with 'dex' and 'cex' price mappings
        """
        return {
            'dex': dict(self.dex_prices),
            'cex': dict(self.cex_prices),
        }


# Example usage
async def main():
    """Example: Monitor both DEX and CEX for arbitrage."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Create manager
    manager = MarketDataManager(
        enable_dex=True,
        enable_cex=True,
        dex_pools=["ETH-USDC-0.3%", "ETH-USDT-0.3%"],
        cex_symbols=["ETH-USDT"],
        arbitrage_threshold_pct=0.3,  # Alert on 0.3%+ difference
    )

    # Register arbitrage callback
    async def handle_arbitrage(data):
        """Handle arbitrage opportunities."""
        print("\n" + "=" * 60)
        print(f"🚨 ARBITRAGE ALERT!")
        print(f"DEX ({data['dex_pool']}): ${data['dex_price']:.2f}")
        print(f"CEX ({data['cex_symbol']}): ${data['cex_price']:.2f}")
        print(f"Difference: {data['price_diff_pct']:.2f}%")
        print(f"Strategy: {data['direction']}")
        print("=" * 60 + "\n")

    manager.on_arbitrage(handle_arbitrage)

    # Start manager
    try:
        await manager.start()
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
