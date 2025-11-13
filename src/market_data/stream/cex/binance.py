"""
CEX (Centralized Exchange) real-time stream handler.

Monitors Binance (and other CEX) order books and trades via WebSocket.
Provides real-time price updates for comparison with DEX prices.
"""

import asyncio
import logging
from decimal import Decimal
from typing import Callable, Optional, Dict, List
from datetime import datetime

from cryptofeed import FeedHandler
from cryptofeed.defines import TRADES, L2_BOOK, BID, ASK
from cryptofeed.exchanges import Binance, BinanceFutures

logger = logging.getLogger(__name__)


class CEXStream:
    """
    Real-time CEX stream handler for centralized exchanges.

    Monitors order book and trades from Binance (spot + futures) for price comparison
    with DEX prices.

    Architecture fit:
    - Part of market_data/stream layer
    - Provides CEX prices for arbitrage detection
    - Emits events to event bus (to be integrated)

    Usage:
        stream = CEXStream(symbols=["BTC-USDT", "ETH-USDT"])
        stream.on_trade(callback_function)
        await stream.start()
    """

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        exchanges: Optional[List[str]] = None
    ):
        """
        Initialize CEX stream.

        Args:
            symbols: List of trading pairs to monitor (e.g., ["BTC-USDT", "ETH-USDT"])
            exchanges: List of exchanges to monitor (default: ["binance"])
        """
        self.symbols = symbols or ["ETH-USDT", "BTC-USDT"]
        self.exchanges = exchanges or ["binance"]

        self.feed_handler = None
        self.trade_callbacks: List[Callable] = []
        self.orderbook_callbacks: List[Callable] = []
        self.current_prices = {}
        self.trade_count = 0
        self._running = False

    async def _handle_trade(self, trade, receipt_timestamp):
        """Handle incoming trade."""
        try:
            self.trade_count += 1

            # Normalize symbol (ETH-USDT, BTC-USDT, etc.)
            symbol = trade.symbol.replace('/', '-')

            trade_data = {
                'exchange': 'BINANCE',
                'symbol': symbol,
                'price': Decimal(str(trade.price)),
                'amount': Decimal(str(trade.amount)),
                'side': trade.side,  # 'buy' or 'sell'
                'timestamp': datetime.fromtimestamp(trade.timestamp),
                'trade_id': trade.id,
            }

            # Update current price
            self.current_prices[symbol] = trade_data['price']

            logger.info(
                f"💹 Trade #{self.trade_count} [{symbol}] | {trade.side.upper()} | "
                f"Price: ${trade.price:.2f} | "
                f"Amount: {trade.amount:.4f}"
            )

            # Notify callbacks
            await self._notify_trade_callbacks(trade_data)

        except Exception as e:
            logger.error(f"Error handling trade: {e}")

    async def _handle_orderbook(self, book, receipt_timestamp):
        """Handle order book update."""
        try:
            symbol = book.symbol.replace('/', '-')

            # Get best bid/ask
            best_bid = max(book.book[BID].keys()) if book.book[BID] else None
            best_ask = min(book.book[ASK].keys()) if book.book[ASK] else None

            if best_bid and best_ask:
                mid_price = (best_bid + best_ask) / 2
                spread = best_ask - best_bid
                spread_bps = (spread / mid_price) * 10000  # basis points

                orderbook_data = {
                    'exchange': 'BINANCE',
                    'symbol': symbol,
                    'best_bid': Decimal(str(best_bid)),
                    'best_ask': Decimal(str(best_ask)),
                    'mid_price': Decimal(str(mid_price)),
                    'spread': Decimal(str(spread)),
                    'spread_bps': Decimal(str(spread_bps)),
                    'timestamp': datetime.now(),
                }

                # Update current price (use mid price)
                self.current_prices[f"{symbol}_mid"] = orderbook_data['mid_price']

                logger.debug(
                    f"📊 OrderBook [{symbol}] | "
                    f"Bid: ${best_bid:.2f} | Ask: ${best_ask:.2f} | "
                    f"Spread: {spread_bps:.2f} bps"
                )

                # Notify callbacks
                await self._notify_orderbook_callbacks(orderbook_data)

        except Exception as e:
            logger.error(f"Error handling orderbook: {e}")

    async def _notify_trade_callbacks(self, trade_data: Dict):
        """Notify all registered trade callbacks."""
        for callback in self.trade_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(trade_data)
                else:
                    callback(trade_data)
            except Exception as e:
                logger.error(f"Error in trade callback: {e}")

    async def _notify_orderbook_callbacks(self, orderbook_data: Dict):
        """Notify all registered orderbook callbacks."""
        for callback in self.orderbook_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(orderbook_data)
                else:
                    callback(orderbook_data)
            except Exception as e:
                logger.error(f"Error in orderbook callback: {e}")

    def on_trade(self, callback: Callable):
        """
        Register callback for trade events.

        Args:
            callback: Function(trade_data) - called on each trade
        """
        self.trade_callbacks.append(callback)

    def on_orderbook(self, callback: Callable):
        """
        Register callback for orderbook updates.

        Args:
            callback: Function(orderbook_data) - called on orderbook update
        """
        self.orderbook_callbacks.append(callback)

    async def start(self):
        """Start CEX stream."""
        self._running = True

        logger.info(f"Starting CEX stream for {len(self.symbols)} symbols...")
        logger.info(f"Monitoring: {', '.join(self.symbols)}")

        # Create feed handler
        self.feed_handler = FeedHandler()

        # Add Binance spot
        if "binance" in self.exchanges:
            # Convert symbols to Binance format (ETH-USDT -> ETH/USDT)
            binance_symbols = [s.replace('-', '/') for s in self.symbols]

            self.feed_handler.add_feed(
                Binance(
                    symbols=binance_symbols,
                    channels=[TRADES],
                    callbacks={
                        TRADES: self._handle_trade
                    }
                )
            )

            logger.info(f"✓ Subscribed to Binance trades")

        # Start feed handler
        try:
            await self.feed_handler.run()
        except Exception as e:
            logger.error(f"Feed handler error: {e}")
            raise

    async def stop(self):
        """Stop CEX stream."""
        self._running = False
        if self.feed_handler:
            try:
                self.feed_handler.stop()
            except (AttributeError, RuntimeError) as e:
                logger.debug(f"CEX feed handler stop error (can be ignored): {e}")
        logger.info("CEX stream stopped")


# Example usage
async def main():
    """Example: Monitor Binance trades in real-time."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Create CEX stream
    stream = CEXStream(symbols=["ETH-USDT", "BTC-USDT"])

    # Register callback
    async def handle_trade(data):
        """Handle trade events."""
        print(f"\n💹 {data['exchange']} {data['symbol']}: ${data['price']:.2f}")
        print(f"   Side: {data['side']}")
        print(f"   Amount: {data['amount']:.4f}")

    stream.on_trade(handle_trade)

    # Start stream
    try:
        await stream.start()
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        await stream.stop()


if __name__ == "__main__":
    asyncio.run(main())
