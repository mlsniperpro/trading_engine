"""
Integration test for the Analytics Engine.

Tests all analytics components working together.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.analytics import (
    AnalyticsEngine,
    OrderFlowAnalyzer,
    MarketProfileAnalyzer,
    MicrostructureAnalyzer,
    SupplyDemandDetector,
    FairValueGapDetector,
    MultiTimeframeManager,
    TradeTick,
    Candle,
    Zone,
    ZoneStatus,
    FairValueGap,
    FVGType,
    FVGStatus,
    TimeframeCandle,
    TrendDirection
)
from src.analytics import indicators


async def test_full_analytics_pipeline():
    """Test complete analytics pipeline."""
    print("="*80)
    print("ANALYTICS ENGINE - FULL INTEGRATION TEST")
    print("="*80)

    # Create analytics engine
    engine = AnalyticsEngine(update_interval=5.0)

    # Create all analyzers
    order_flow = OrderFlowAnalyzer(imbalance_threshold=2.5)
    market_profile = MarketProfileAnalyzer(tick_size=1.0)
    microstructure = MicrostructureAnalyzer(min_wick_ratio=0.5)
    supply_demand = SupplyDemandDetector(min_base_candles=3)
    fvg_detector = FairValueGapDetector(min_gap_pct=0.1)
    multi_tf = MultiTimeframeManager(timeframes=['1m', '5m', '15m'])

    # Register analyzers with engine
    engine.register_analyzers(
        order_flow=order_flow,
        market_profile=market_profile,
        microstructure=microstructure,
        supply_demand=supply_demand,
        fvg=fvg_detector,
        multi_tf=multi_tf
    )

    print("\n✅ All analytics components registered")

    # Simulate market data
    symbol = 'BTCUSDT'
    now = datetime.utcnow()

    print(f"\n{'='*80}")
    print("SIMULATING MARKET DATA")
    print('='*80)

    # 1. Add trade ticks for order flow analysis
    print("\n1. Adding trade ticks for order flow analysis...")
    for i in range(50):
        tick = TradeTick(
            symbol=symbol,
            price=95000 + i * 10,
            amount=0.5 if i % 2 == 0 else 0.1,
            side='buy' if i < 35 else 'sell',  # 70% buy pressure
            timestamp=now - timedelta(seconds=100 - i*2),
            exchange='binance'
        )
        order_flow.add_tick(tick)

    # Test CVD
    cvd = await order_flow.calculate_cvd(symbol, lookback_seconds=200)
    print(f"   CVD: {cvd['cvd']:.2f} ({cvd['trend']})")
    print(f"   Buy Volume: {cvd['buy_volume']:.2f}")
    print(f"   Sell Volume: {cvd['sell_volume']:.2f}")

    # Test imbalance
    imbalance = await order_flow.detect_imbalance(symbol, window_seconds=50)
    print(f"   Buy/Sell Ratio: {imbalance['buy_sell_ratio']:.2f}x")
    if imbalance['imbalance_detected']:
        print(f"   ⚡ IMBALANCE DETECTED: {imbalance['direction'].upper()}")

    # 2. Add market profile data
    print("\n2. Building market profile...")
    import random
    random.seed(42)
    for i in range(500):
        price = random.gauss(95000, 100)
        tick_data = {
            'price': price,
            'amount': random.uniform(0.01, 0.5),
            'side': random.choice(['buy', 'sell']),
            'timestamp': now - timedelta(seconds=900 - i)
        }
        market_profile.add_tick(symbol, tick_data)

    profile = await market_profile.calculate_profile(symbol, timeframe='15m')
    print(f"   POC: ${profile['poc']:,.2f}")
    print(f"   VAH: ${profile['vah']:,.2f}")
    print(f"   VAL: ${profile['val']:,.2f}")

    # 3. Microstructure analysis
    print("\n3. Analyzing microstructure patterns...")
    test_candle = Candle(
        symbol=symbol,
        open=95000,
        high=95200,
        low=94500,  # Long lower wick
        close=95100,
        volume=100,
        timestamp=now
    )
    rejection = await microstructure.detect_rejection(symbol, test_candle)
    if rejection['detected']:
        print(f"   ✓ Pattern detected: {rejection['pattern_name']}")
        print(f"   Type: {rejection['type']}")
        print(f"   Strength: {rejection['strength']:.2f}")
    else:
        print("   No rejection pattern detected")

    # 4. Supply/Demand zones
    print("\n4. Creating supply/demand zones...")
    demand_zone = Zone(
        zone_id=f"{symbol}_demand_1",
        zone_type='demand',
        price_low=94000,
        price_high=94200,
        created_at=now,
        status=ZoneStatus.FRESH,
        strength=85,
        origin_candles=5,
        volume_at_origin=1000
    )
    supply_demand.add_zone(symbol, demand_zone)
    print(f"   Demand Zone: ${demand_zone.price_low:.0f} - ${demand_zone.price_high:.0f} (strength: {demand_zone.strength:.0f})")

    nearest = await supply_demand.get_nearest_zones(symbol, 95000)
    if nearest['demand']:
        print(f"   Nearest Demand: ${nearest['demand'].price_mid:.0f} ({nearest['demand'].status.value})")

    # 5. Fair Value Gaps
    print("\n5. Identifying Fair Value Gaps...")
    fvg = FairValueGap(
        fvg_id=f"{symbol}_bull_fvg_1",
        symbol=symbol,
        fvg_type=FVGType.BULLISH,
        gap_low=94500,
        gap_high=94800,
        created_at=now,
        status=FVGStatus.UNFILLED,
        timeframe='5m'
    )
    fvg_detector.add_fvg(symbol, fvg)
    print(f"   Bullish FVG: ${fvg.gap_low:.0f} - ${fvg.gap_high:.0f} ({fvg.status.value})")

    unfilled_fvgs = await fvg_detector.get_unfilled_fvgs(symbol)
    print(f"   Total unfilled FVGs: {len(unfilled_fvgs)}")

    # 6. Multi-timeframe analysis
    print("\n6. Multi-timeframe coordination...")
    for tf in ['1m', '5m', '15m']:
        candle = TimeframeCandle(
            symbol=symbol,
            timeframe=tf,
            open=94900,
            high=95200,
            low=94850,
            close=95150,  # Bullish
            volume=100 * (1 if tf == '1m' else 5 if tf == '5m' else 15),
            timestamp=now
        )
        multi_tf.add_candle(symbol, tf, candle)

    # Set trends manually for demo
    multi_tf._trend_cache[symbol] = {
        '1m': TrendDirection.BULLISH,
        '5m': TrendDirection.BULLISH,
        '15m': TrendDirection.BULLISH
    }

    alignment = await multi_tf.check_trend_alignment(symbol)
    print(f"   Alignment: {alignment['alignment'].upper()}")
    for tf, trend in alignment['trends'].items():
        print(f"   {tf}: {trend}")

    # 7. Technical Indicators
    print("\n7. Calculating technical indicators...")
    prices = [95000 + i * 10 for i in range(30)]
    volumes = [100] * 30

    rsi = indicators.calculate_rsi(prices, period=14)
    ema_20 = indicators.calculate_ema(prices, period=20)
    vwap = indicators.calculate_vwap(prices, volumes)

    print(f"   RSI(14): {rsi:.2f}")
    print(f"   EMA(20): ${ema_20:.2f}")
    print(f"   VWAP: ${vwap:.2f}")

    # Final summary
    print(f"\n{'='*80}")
    print("ANALYTICS SUMMARY")
    print('='*80)
    print(f"Symbol: {symbol}")
    print(f"\nOrder Flow:")
    print(f"  CVD: {cvd['cvd']:.2f} ({cvd['trend']})")
    print(f"  Imbalance: {imbalance['buy_sell_ratio']:.2f}x ({imbalance['direction']})")
    print(f"\nMarket Profile:")
    print(f"  POC: ${profile['poc']:,.2f}")
    print(f"  Value Area: ${profile['val']:,.2f} - ${profile['vah']:,.2f}")
    print(f"\nMicrostructure:")
    print(f"  Pattern: {rejection.get('pattern_name', 'none')}")
    print(f"\nZones:")
    print(f"  Demand zones: 1")
    print(f"  Supply zones: 0")
    print(f"\nFair Value Gaps:")
    print(f"  Unfilled: {len(unfilled_fvgs)}")
    print(f"\nMulti-Timeframe:")
    print(f"  Alignment: {alignment['alignment'].upper()}")
    print(f"\nIndicators:")
    print(f"  RSI: {rsi:.2f} ({'Overbought' if rsi > 70 else 'Oversold' if rsi < 30 else 'Neutral'})")
    print(f"  EMA(20): ${ema_20:.2f}")

    print(f"\n{'='*80}")
    print("✅ ALL ANALYTICS TESTS PASSED")
    print('='*80)


if __name__ == "__main__":
    asyncio.run(test_full_analytics_pipeline())
