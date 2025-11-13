"""
Example: Monitor DEX and CEX for arbitrage opportunities.

This demonstrates the new market_data/stream architecture:
- DEXStream: Monitors Uniswap V3 pools
- CEXStream: Monitors Binance spot
- MarketDataManager: Coordinates both and detects arbitrage

Usage:
    uv run python examples/monitor_dex_cex_arbitrage.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from market_data.stream import MarketDataManager


async def main():
    """Monitor both DEX and CEX for arbitrage opportunities."""

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("\n" + "=" * 70)
    print("🔍 DEX/CEX Arbitrage Monitor")
    print("=" * 70)
    print("\nMonitoring:")
    print("  • DEX: Uniswap V3 (ETH-USDC-0.3%, ETH-USDT-0.3%)")
    print("  • CEX: Binance Spot (ETH-USDT)")
    print("  • Arbitrage threshold: 0.3%")
    print("\nPress Ctrl+C to stop...")
    print("=" * 70 + "\n")

    # Create manager
    manager = MarketDataManager(
        enable_uniswap_v3=True,
        enable_binance=True,
        uniswap_pools=["ETH-USDC-0.3%", "ETH-USDT-0.3%"],
        binance_symbols=["ETH-USDT"],
        arbitrage_threshold_pct=0.3,  # Alert on 0.3%+ difference
    )

    # Register arbitrage callback
    async def handle_arbitrage(data):
        """Handle arbitrage opportunities."""
        print("\n" + "🚨" * 30)
        print(f"🚨 ARBITRAGE OPPORTUNITY DETECTED!")
        print("🚨" * 30)
        print(f"\n📊 Price Comparison:")
        print(f"   DEX ({data['dex_pool']}): ${data['dex_price']:.2f}")
        print(f"   CEX ({data['cex_symbol']}): ${data['cex_price']:.2f}")
        print(f"\n💰 Opportunity:")
        print(f"   Price Difference: ${data['price_diff']:.2f} ({data['price_diff_pct']:.2f}%)")
        print(f"   Strategy: {data['direction']}")
        print(f"\n⚡ Action:")
        if data['direction'] == 'BUY_CEX_SELL_DEX':
            print(f"   1. Buy ETH on Binance at ${data['cex_price']:.2f}")
            print(f"   2. Sell ETH on Uniswap at ${data['dex_price']:.2f}")
            print(f"   3. Profit: ~${data['price_diff']:.2f} per ETH")
        else:
            print(f"   1. Buy ETH on Uniswap at ${data['dex_price']:.2f}")
            print(f"   2. Sell ETH on Binance at ${data['cex_price']:.2f}")
            print(f"   3. Profit: ~${data['price_diff']:.2f} per ETH")
        print("\n" + "🚨" * 30 + "\n")

    # Register unified price callback (optional - for monitoring)
    async def handle_price(data):
        """Log all price updates."""
        if data['source'] == 'DEX':
            # Only log every 10th DEX swap to reduce noise
            pass
        else:
            # Log CEX trades
            logging.debug(
                f"{data['source']} | {data['pair']} | ${data['price']:.2f}"
            )

    manager.on_arbitrage(handle_arbitrage)
    manager.on_price(handle_price)

    # Start manager
    try:
        await manager.start()
    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print("⏹  Shutting down...")
        print("=" * 70)
        await manager.stop()

        # Print summary
        prices = manager.get_current_prices()
        print("\n📊 Final Prices:")
        print("\nDEX (Uniswap V3):")
        for pool, price in prices['dex'].items():
            print(f"   {pool}: ${price:.2f}")
        print("\nCEX (Binance):")
        for symbol, price in prices['cex'].items():
            print(f"   {symbol}: ${price:.2f}")
        print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

