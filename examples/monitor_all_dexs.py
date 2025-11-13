#!/usr/bin/env python3
"""
Monitor all DEX streams simultaneously.

This example demonstrates monitoring all supported DEX protocols:
- Uniswap V3
- Curve Finance
- SushiSwap
- Balancer V2

Plus CEX (Binance) for arbitrage detection.
"""

import asyncio
import logging
from datetime import datetime

from market_data.stream import MarketDataManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Monitor all DEX exchanges + CEX."""

    print("\n" + "=" * 80)
    print("🚀 Multi-DEX + CEX Arbitrage Monitor")
    print("=" * 80)
    print("\nMonitoring:")
    print("  • Uniswap V3  - ETH-USDC-0.3%, ETH-USDT-0.3%")
    print("  • Curve       - stETH pool, frxETH pool")
    print("  • SushiSwap   - ETH-USDC, ETH-USDT")
    print("  • Balancer V2 - BAL-WETH pool")
    print("  • Binance CEX - ETH-USDT")
    print("\n" + "=" * 80 + "\n")

    # Create manager with ALL DEXs enabled
    manager = MarketDataManager(
        # Uniswap V3
        enable_uniswap_v3=True,
        uniswap_pools=["ETH-USDC-0.3%", "ETH-USDT-0.3%"],

        # Curve Finance
        enable_curve=True,
        curve_pools=["stETH", "frxETH"],

        # SushiSwap
        enable_sushiswap=True,
        sushiswap_pairs=["ETH-USDC", "ETH-USDT"],

        # Balancer V2
        enable_balancer=True,
        balancer_pools=["BAL-WETH"],

        # Binance CEX
        enable_binance=True,
        binance_symbols=["ETH-USDT"],

        # Arbitrage settings
        arbitrage_threshold_pct=0.3,  # Alert on 0.3%+ difference
    )

    # Track statistics
    stats = {
        'uniswap_swaps': 0,
        'curve_swaps': 0,
        'sushiswap_swaps': 0,
        'balancer_swaps': 0,
        'cex_trades': 0,
        'arbitrage_opportunities': 0,
        'start_time': datetime.now()
    }

    # Register price callback to track statistics
    async def track_stats(price_data):
        """Track statistics for each exchange."""
        venue = price_data.get('venue', '')

        if venue == 'UNISWAP_V3':
            stats['uniswap_swaps'] += 1
        elif venue == 'CURVE':
            stats['curve_swaps'] += 1
        elif venue == 'SUSHISWAP':
            stats['sushiswap_swaps'] += 1
        elif venue == 'BALANCER':
            stats['balancer_swaps'] += 1
        elif venue == 'BINANCE':
            stats['cex_trades'] += 1

    manager.on_price(track_stats)

    # Register arbitrage callback
    async def handle_arbitrage(data):
        """Handle arbitrage opportunities."""
        stats['arbitrage_opportunities'] += 1

        print("\n" + "🚨" * 40)
        print(f"ARBITRAGE OPPORTUNITY #{stats['arbitrage_opportunities']}")
        print("🚨" * 40)
        print(f"  DEX: {data.get('dex_pool', 'N/A')} @ ${data['dex_price']:.2f}")
        print(f"  CEX: {data.get('cex_symbol', 'N/A')} @ ${data['cex_price']:.2f}")
        print(f"  Difference: {data['price_diff_pct']:.2f}%")
        print(f"  Strategy: {data['direction']}")
        print("🚨" * 40 + "\n")

    manager.on_arbitrage(handle_arbitrage)

    # Print statistics periodically
    async def print_stats():
        """Print statistics every 60 seconds."""
        while True:
            await asyncio.sleep(60)

            elapsed = (datetime.now() - stats['start_time']).total_seconds()

            print("\n" + "=" * 80)
            print("📊 STATISTICS (Last 60 seconds)")
            print("=" * 80)
            print(f"  Runtime: {elapsed:.0f}s")
            print(f"  Uniswap V3:  {stats['uniswap_swaps']} swaps")
            print(f"  Curve:       {stats['curve_swaps']} swaps")
            print(f"  SushiSwap:   {stats['sushiswap_swaps']} swaps")
            print(f"  Balancer V2: {stats['balancer_swaps']} swaps")
            print(f"  Binance CEX: {stats['cex_trades']} trades")
            print(f"  Arbitrage:   {stats['arbitrage_opportunities']} opportunities")
            print("=" * 80 + "\n")

            # Reset counters
            stats['uniswap_swaps'] = 0
            stats['curve_swaps'] = 0
            stats['sushiswap_swaps'] = 0
            stats['balancer_swaps'] = 0
            stats['cex_trades'] = 0
            stats['arbitrage_opportunities'] = 0

    # Start stats printer in background
    asyncio.create_task(print_stats())

    # Start manager
    try:
        await manager.start()
    except KeyboardInterrupt:
        logger.info("\n\nShutting down...")
        await manager.stop()

        # Final statistics
        elapsed = (datetime.now() - stats['start_time']).total_seconds()
        print("\n" + "=" * 80)
        print("📊 FINAL STATISTICS")
        print("=" * 80)
        print(f"  Total runtime: {elapsed:.0f}s")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
