"""
Unified price feed combining CEX (Centralized) and DEX (Decentralized) data.

CEX Data: Binance, Coinbase, Kraken via CryptoFeed (WebSocket)
DEX Data: Uniswap V3 via Alchemy (On-chain events)

Enables:
- Cross-exchange arbitrage detection
- Price comparison across CEX and DEX
- Decentralized + Centralized data for robust trading
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, Callable
from datetime import datetime

# Import our price feeds
from trading_engine.price_feed import MultiExchangePriceFeed
from trading_engine.dex_feed import DEXPriceFeed

logger = logging.getLogger(__name__)


class UnifiedPriceFeed:
    """
    Unified price feed combining CEX and DEX data.

    Features:
    - Real-time prices from 4 CEXs (Binance, Coinbase, Kraken, Bybit)
    - Real-time prices from Uniswap V3 (on-chain)
    - Arbitrage opportunity detection
    - Price aggregation and comparison
    - 100% FREE (uses free tiers)
    """

    def __init__(self, symbols: list[str] = None):
        """
        Initialize unified feed.

        Args:
            symbols: Trading pairs to monitor (e.g., ['ETH-USDT', 'BTC-USDT'])
        """
        self.symbols = symbols or ['ETH-USDT']

        # Initialize feeds
        self.cex_feed = MultiExchangePriceFeed(symbols=self.symbols)
        self.dex_feed = DEXPriceFeed()

        # Price tracking
        self.latest_prices: Dict[str, Dict] = {
            'cex': {},  # {exchange:symbol -> price_data}
            'dex': {}   # {pair -> price_data}
        }

        # Statistics
        self.arbitrage_opportunities = 0
        self.total_updates = 0

        # Callbacks
        self.price_callbacks: list[Callable] = []
        self.arbitrage_callbacks: list[Callable] = []

    async def _on_cex_update(self, data: Dict):
        """Handle CEX price updates."""
        key = f"{data['exchange']}:{data['symbol']}"
        self.latest_prices['cex'][key] = data
        self.total_updates += 1

        # Check for arbitrage
        await self._check_arbitrage('cex', data)

        # Notify callbacks
        await self._notify_price_callbacks(data)

    async def _on_dex_update(self, data: Dict):
        """Handle DEX price updates."""
        key = f"{data['exchange']}:{data['pair']}"
        self.latest_prices['dex'][key] = data
        self.total_updates += 1

        # Check for arbitrage
        await self._check_arbitrage('dex', data)

        # Notify callbacks
        await self._notify_price_callbacks(data)

    async def _check_arbitrage(self, source: str, data: Dict):
        """
        Check for arbitrage opportunities between CEX and DEX.

        Example: If Binance ETH = $3000 and Uniswap ETH = $3020,
                 there's a $20 arbitrage opportunity!
        """
        try:
            # Only check for ETH-USDT / ETH-USDC pairs
            symbol = data.get('symbol') or data.get('pair')
            if 'ETH' not in symbol:
                return

            price = data['price']

            # Compare with other sources
            if source == 'cex':
                # Compare CEX price with DEX
                dex_prices = [
                    p for k, p in self.latest_prices['dex'].items()
                    if 'ETH' in k
                ]
                for dex_data in dex_prices:
                    diff = abs(price - dex_data['price'])
                    diff_pct = (diff / price) * 100

                    if diff_pct > 0.5:  # >0.5% difference = arbitrage!
                        self.arbitrage_opportunities += 1
                        await self._notify_arbitrage({
                            'cex_exchange': data['exchange'],
                            'cex_price': price,
                            'dex_exchange': dex_data['exchange'],
                            'dex_price': dex_data['price'],
                            'difference': diff,
                            'difference_pct': diff_pct,
                            'timestamp': datetime.now()
                        })

            elif source == 'dex':
                # Compare DEX price with CEX
                cex_prices = [
                    p for k, p in self.latest_prices['cex'].items()
                    if 'ETH' in k
                ]
                for cex_data in cex_prices:
                    diff = abs(price - cex_data['price'])
                    diff_pct = (diff / price) * 100

                    if diff_pct > 0.5:  # >0.5% difference = arbitrage!
                        self.arbitrage_opportunities += 1
                        await self._notify_arbitrage({
                            'cex_exchange': cex_data['exchange'],
                            'cex_price': cex_data['price'],
                            'dex_exchange': data['exchange'],
                            'dex_price': price,
                            'difference': diff,
                            'difference_pct': diff_pct,
                            'timestamp': datetime.now()
                        })

        except Exception as e:
            logger.error(f"Error checking arbitrage: {e}")

    async def _notify_price_callbacks(self, data: Dict):
        """Notify price update callbacks."""
        for callback in self.price_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Error in price callback: {e}")

    async def _notify_arbitrage(self, arb_data: Dict):
        """Notify arbitrage callbacks."""
        logger.warning(
            f"🚨 ARBITRAGE! "
            f"{arb_data['cex_exchange']}: ${arb_data['cex_price']:.2f} | "
            f"{arb_data['dex_exchange']}: ${arb_data['dex_price']:.2f} | "
            f"Diff: ${arb_data['difference']:.2f} ({arb_data['difference_pct']:.2f}%)"
        )

        for callback in self.arbitrage_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(arb_data)
                else:
                    callback(arb_data)
            except Exception as e:
                logger.error(f"Error in arbitrage callback: {e}")

    def on_price_update(self, callback: Callable):
        """Register callback for all price updates (CEX + DEX)."""
        self.price_callbacks.append(callback)

    def on_arbitrage(self, callback: Callable):
        """Register callback for arbitrage opportunities."""
        self.arbitrage_callbacks.append(callback)

    def get_latest_price(self, source: str, exchange: str, symbol: str) -> Dict:
        """
        Get latest price from a specific source/exchange.

        Args:
            source: 'cex' or 'dex'
            exchange: Exchange name (e.g., 'BINANCE' or 'UNISWAP_V3')
            symbol: Trading pair (e.g., 'ETH-USDT')

        Returns:
            Price data dict or None
        """
        key = f"{exchange}:{symbol}"
        return self.latest_prices[source].get(key)

    def get_all_eth_prices(self) -> Dict:
        """Get all current ETH prices across CEX and DEX."""
        eth_prices = {
            'cex': {},
            'dex': {}
        }

        for key, data in self.latest_prices['cex'].items():
            if 'ETH' in key:
                eth_prices['cex'][key] = data['price']

        for key, data in self.latest_prices['dex'].items():
            if 'ETH' in key:
                eth_prices['dex'][key] = data['price']

        return eth_prices

    async def start(self):
        """Start unified feed (CEX + DEX)."""
        logger.info("Starting unified price feed (CEX + DEX)...")

        # Register internal callbacks
        self.cex_feed.on_price_update(self._on_cex_update)
        self.dex_feed.on_price_update(self._on_dex_update)

        # Start both feeds concurrently
        await asyncio.gather(
            asyncio.to_thread(self.cex_feed.start),  # CryptoFeed runs in thread
            self.dex_feed.start()  # DEX feed is async
        )

    def stop(self):
        """Stop unified feed."""
        self.cex_feed.stop()
        asyncio.create_task(self.dex_feed.stop())
        logger.info("Unified price feed stopped")


# Example usage
async def main():
    """Example: Monitor CEX + DEX prices and detect arbitrage."""

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Create unified feed
    feed = UnifiedPriceFeed(symbols=['ETH-USDT'])

    # Define arbitrage strategy
    async def arbitrage_alert(arb_data):
        """
        Alert when arbitrage opportunity detected.

        In production, this would:
        1. Verify liquidity on both exchanges
        2. Calculate fees and slippage
        3. Execute arbitrage trade if profitable
        4. Monitor execution and manage risk
        """
        print(f"\n" + "="*60)
        print(f"🚨 ARBITRAGE OPPORTUNITY DETECTED!")
        print(f"="*60)
        print(f"CEX ({arb_data['cex_exchange']}): ${arb_data['cex_price']:.2f}")
        print(f"DEX ({arb_data['dex_exchange']}): ${arb_data['dex_price']:.2f}")
        print(f"Difference: ${arb_data['difference']:.2f} ({arb_data['difference_pct']:.2f}%)")
        print(f"="*60 + "\n")

        # Example: Check if profitable after fees
        # gas_cost = 15  # $15 gas for Ethereum
        # cex_fee = arb_data['difference'] * 0.001  # 0.1% fee
        # net_profit = arb_data['difference'] - gas_cost - cex_fee
        # if net_profit > 10:
        #     print(f"✅ PROFITABLE! Net: ${net_profit:.2f}")
        #     # Execute arbitrage trade here

    # Register callback
    feed.on_arbitrage(arbitrage_alert)

    # Start feed
    try:
        print("\n🚀 Starting unified price feed...")
        print("📊 Monitoring: 4 CEXs + Uniswap V3")
        print("🔍 Detecting: Arbitrage opportunities\n")
        await feed.start()
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        feed.stop()


if __name__ == "__main__":
    asyncio.run(main())
