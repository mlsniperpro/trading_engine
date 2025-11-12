"""
Real-time cryptocurrency price feed using CryptoFeed.
Supports 40+ exchanges via WebSocket with normalized data format.
"""

import asyncio
import logging
from decimal import Decimal
from typing import Callable, Optional, Dict
from datetime import datetime

from cryptofeed import FeedHandler
from cryptofeed.defines import TRADES, L2_BOOK, TICKER
from cryptofeed.exchanges import Binance, Coinbase, Kraken, Bybit

logger = logging.getLogger(__name__)


class MultiExchangePriceFeed:
    """
    Real-time multi-exchange cryptocurrency price feed using CryptoFeed.

    Features:
    - WebSocket connections to multiple exchanges
    - Normalized data format across all exchanges
    - Real-time trades, orderbook, and ticker updates
    - Automatic reconnection and error handling
    - Completely FREE (no API keys needed for public data)
    """

    def __init__(self, symbols: list[str] = None):
        """
        Initialize multi-exchange price feed.

        Args:
            symbols: List of trading pairs (e.g., ['ETH-USDT', 'BTC-USDT'])
                    If None, defaults to ['ETH-USDT']
        """
        self.symbols = symbols or ['ETH-USDT']
        self.feed_handler = FeedHandler()

        # Price tracking
        self.latest_prices: Dict[str, Dict[str, Decimal]] = {}
        self.price_callbacks: list[Callable] = []

        # Statistics
        self.trade_count = 0
        self.update_count = 0

    async def on_trade(self, trade, receipt_timestamp):
        """
        Handle trade updates from any exchange.

        Args:
            trade: Trade object with normalized fields:
                - exchange: str (e.g., 'BINANCE')
                - symbol: str (e.g., 'ETH-USDT')
                - side: str ('buy' or 'sell')
                - amount: Decimal
                - price: Decimal
                - timestamp: float
            receipt_timestamp: When we received the data
        """
        self.trade_count += 1

        # Update latest price
        key = f"{trade.exchange}:{trade.symbol}"
        if key not in self.latest_prices:
            self.latest_prices[key] = {}

        self.latest_prices[key] = {
            'price': Decimal(str(trade.price)),
            'amount': Decimal(str(trade.amount)),
            'side': trade.side,
            'exchange': trade.exchange,
            'symbol': trade.symbol,
            'timestamp': datetime.fromtimestamp(trade.timestamp)
        }

        logger.info(
            f"💰 {trade.exchange} {trade.symbol} - "
            f"${trade.price:.2f} ({trade.side.upper()}) "
            f"Amount: {trade.amount:.4f}"
        )

        # Notify callbacks
        await self._notify_callbacks(self.latest_prices[key])

    async def on_ticker(self, ticker, receipt_timestamp):
        """
        Handle ticker updates (best bid/ask).

        Args:
            ticker: Ticker object with:
                - exchange, symbol, bid, ask, timestamp
        """
        self.update_count += 1

        logger.debug(
            f"📊 {ticker.exchange} {ticker.symbol} - "
            f"Bid: ${ticker.bid:.2f} Ask: ${ticker.ask:.2f}"
        )

    async def on_book(self, book, receipt_timestamp):
        """
        Handle orderbook updates.

        Args:
            book: Book object with bids and asks
        """
        # Get best bid and ask
        if book.book.bids and book.book.asks:
            best_bid = list(book.book.bids.keys())[-1]
            best_ask = list(book.book.asks.keys())[0]

            spread = best_ask - best_bid
            spread_pct = (spread / best_ask) * 100

            logger.debug(
                f"📖 {book.exchange} {book.symbol} - "
                f"Spread: ${spread:.2f} ({spread_pct:.3f}%)"
            )

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
        Register a callback for price updates.

        Args:
            callback: Function(price_data) - called on each trade

        Example:
            async def my_strategy(data):
                print(f"{data['exchange']}: ${data['price']}")

            feed.on_price_update(my_strategy)
        """
        self.price_callbacks.append(callback)

    def get_latest_price(self, exchange: str, symbol: str) -> Optional[Dict]:
        """
        Get latest cached price for an exchange/symbol pair.

        Args:
            exchange: Exchange name (e.g., 'BINANCE')
            symbol: Trading pair (e.g., 'ETH-USDT')

        Returns:
            Dict with price, amount, side, timestamp or None
        """
        key = f"{exchange}:{symbol}"
        return self.latest_prices.get(key)

    def start(self):
        """
        Start real-time price feed from multiple exchanges.

        Connects to:
        - Binance (largest crypto exchange)
        - Coinbase (US-regulated)
        - Kraken (EU-based)
        - Bybit (derivatives focus)

        All via WebSocket - completely FREE!
        """
        logger.info(f"Starting price feed for {self.symbols}")

        # Binance - Largest exchange, best liquidity
        self.feed_handler.add_feed(
            Binance(
                symbols=self.symbols,
                channels=[TRADES],
                callbacks={TRADES: self.on_trade}
            )
        )

        # Coinbase - US-regulated, good for compliance
        self.feed_handler.add_feed(
            Coinbase(
                symbols=self.symbols,
                channels=[TRADES],
                callbacks={TRADES: self.on_trade}
            )
        )

        # Kraken - European exchange, good backup
        self.feed_handler.add_feed(
            Kraken(
                symbols=self.symbols,
                channels=[TRADES],
                callbacks={TRADES: self.on_trade}
            )
        )

        # Bybit - Good for derivatives data
        self.feed_handler.add_feed(
            Bybit(
                symbols=self.symbols,
                channels=[TRADES],
                callbacks={TRADES: self.on_trade}
            )
        )

        logger.info("✓ Connected to 4 exchanges via WebSocket")
        logger.info("✓ Real-time trade data streaming...")

        # Run the feed
        self.feed_handler.run()

    def stop(self):
        """Stop the price feed."""
        self.feed_handler.stop()
        logger.info("Price feed stopped")


# Example usage
async def main():
    """Example: Monitor ETH and BTC prices across multiple exchanges."""

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Create multi-exchange feed
    feed = MultiExchangePriceFeed(symbols=['ETH-USDT', 'BTC-USDT'])

    # Define trading strategy callback
    async def my_trading_strategy(data):
        """
        Example callback - implement your trading logic here.

        Args:
            data: Dict with keys:
                - price: Decimal
                - amount: Decimal
                - side: str ('buy' or 'sell')
                - exchange: str
                - symbol: str
                - timestamp: datetime
        """
        price = data['price']
        exchange = data['exchange']
        symbol = data['symbol']

        print(f"\n🔔 {exchange} - {symbol}: ${price}")

        # Example: Simple price alert
        if symbol == 'ETH-USDT':
            if price < 3000:
                print("🟢 ETH below $3000 - Potential BUY")
            elif price > 3500:
                print("🔴 ETH above $3500 - Potential SELL")

        # Example: Cross-exchange arbitrage detection
        # (In real implementation, you'd compare prices across exchanges)

    # Register callback
    feed.on_price_update(my_trading_strategy)

    # Start feed (this blocks and runs forever)
    try:
        feed.start()
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        feed.stop()


if __name__ == "__main__":
    asyncio.run(main())
