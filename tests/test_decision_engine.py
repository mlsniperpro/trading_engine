"""
Test script for Decision Engine.

Tests signal generation with various market scenarios:
1. Strong bullish signal (high confluence)
2. Weak signal (low confluence - rejected)
3. Primary analyzer failure (rejected)
4. Directional conflict (rejected)
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from decision import create_default_decision_engine, TradeSignal


# Mock data structures
@dataclass
class MockCandle:
    """Mock 1-minute candle data."""
    open: float
    high: float
    low: float
    close: float


@dataclass
class MockMarketProfile:
    """Mock market profile data."""
    value_area_high: float
    value_area_low: float
    point_of_control: float


@dataclass
class MockZone:
    """Mock supply/demand zone."""
    price_low: float
    price_high: float
    is_fresh: bool = True
    test_count: int = 0


@dataclass
class MockFVG:
    """Mock fair value gap."""
    gap_low: float
    gap_high: float
    is_filled: bool = False
    direction: str = 'bullish'


@dataclass
class MockMarketData:
    """Mock market data for testing."""
    symbol: str
    current_price: float

    # Order flow data
    buy_volume_30s: float
    sell_volume_30s: float

    # Microstructure data
    latest_candle_1m: MockCandle

    # Market profile data
    market_profile_15m: MockMarketProfile

    # Mean reversion data
    price_mean_15m: float
    price_std_dev_15m: float

    # Autocorrelation
    price_autocorrelation: float

    # Zones
    demand_zones: list
    supply_zones: list

    # FVGs
    fair_value_gaps: list


def create_strong_bullish_signal() -> MockMarketData:
    """
    Create market data that should generate a STRONG LONG signal.

    PRIMARY SIGNALS:
    - Order flow: 3.5:1 buy/sell ratio (✅ pass, threshold 2.5)
    - Microstructure: Bullish rejection pattern (✅ pass)

    SECONDARY FILTERS:
    - Market Profile: At VAL (+1.5 points)
    - Mean Reversion: Beyond 2σ (+1.5 points)
    - Autocorrelation: Low 0.2 (+1.0 point)
    - Demand Zone: Fresh zone (+2.0 points)
    - Supply Zone: Target above (+0.5 points)
    - FVG: Unfilled bullish gap (+1.5 points)

    TOTAL: 8.0/8.0 points (100%) - VERY HIGH confidence
    """
    return MockMarketData(
        symbol='BTCUSDT',
        current_price=50250.0,

        # Strong bullish order flow (3.5:1)
        buy_volume_30s=350000,
        sell_volume_30s=100000,

        # Bullish rejection candle
        latest_candle_1m=MockCandle(
            open=50240.0,
            high=50260.0,
            low=50200.0,  # Long lower wick
            close=50255.0  # Close near high
        ),

        # At Value Area Low (reversal zone)
        market_profile_15m=MockMarketProfile(
            value_area_high=50500.0,
            value_area_low=50250.0,  # Current price at VAL
            point_of_control=50400.0
        ),

        # Price -2.1σ below mean (extreme deviation)
        price_mean_15m=50400.0,
        price_std_dev_15m=71.0,  # 50250 is ~2.1σ below 50400

        # Low autocorrelation (mean reverting market)
        price_autocorrelation=0.2,

        # Fresh demand zone at current price
        demand_zones=[
            MockZone(price_low=50200.0, price_high=50260.0, is_fresh=True)
        ],

        # Supply zone above as target
        supply_zones=[
            MockZone(price_low=50500.0, price_high=50550.0, is_fresh=False)
        ],

        # Unfilled bullish FVG
        fair_value_gaps=[
            MockFVG(gap_low=50240.0, gap_high=50270.0, is_filled=False, direction='bullish')
        ]
    )


def create_weak_signal() -> MockMarketData:
    """
    Create market data that should be REJECTED (insufficient confluence).

    PRIMARY SIGNALS:
    - Order flow: 2.8:1 buy/sell ratio (✅ pass, but weak)
    - Microstructure: Bullish rejection (✅ pass)

    SECONDARY FILTERS:
    - Market Profile: Inside value area (+0.5 points)
    - Mean Reversion: Inside 1σ (0 points)
    - Autocorrelation: Moderate 0.45 (+0.5 points)
    - Demand Zone: No zone (0 points)
    - Supply Zone: No target (0 points)
    - FVG: Filled gap (0 points)

    TOTAL: 1.0/8.0 points (12.5%) - Below 3.0 threshold
    """
    return MockMarketData(
        symbol='BTCUSDT',
        current_price=50350.0,

        # Weak bullish flow (2.8:1)
        buy_volume_30s=280000,
        sell_volume_30s=100000,

        # Small rejection candle
        latest_candle_1m=MockCandle(
            open=50340.0,
            high=50360.0,
            low=50330.0,
            close=50355.0
        ),

        # Inside value area (not at extremes)
        market_profile_15m=MockMarketProfile(
            value_area_high=50500.0,
            value_area_low=50250.0,
            point_of_control=50375.0
        ),

        # Price near mean (no extreme)
        price_mean_15m=50360.0,
        price_std_dev_15m=50.0,  # Only 0.2σ away

        # Moderate autocorrelation
        price_autocorrelation=0.45,

        # No zones
        demand_zones=[],
        supply_zones=[],

        # Filled FVG
        fair_value_gaps=[
            MockFVG(gap_low=50300.0, gap_high=50350.0, is_filled=True)
        ]
    )


def create_failed_primary() -> MockMarketData:
    """
    Create market data where PRIMARY signals fail.

    PRIMARY SIGNALS:
    - Order flow: 1.5:1 buy/sell ratio (❌ FAIL - below 2.5 threshold)
    - Microstructure: No rejection pattern (❌ FAIL)

    Should be rejected immediately without checking secondary filters.
    """
    return MockMarketData(
        symbol='BTCUSDT',
        current_price=50350.0,

        # Balanced flow (1.5:1 - below threshold)
        buy_volume_30s=150000,
        sell_volume_30s=100000,

        # No rejection pattern (normal candle)
        latest_candle_1m=MockCandle(
            open=50340.0,
            high=50360.0,
            low=50335.0,  # Small wick
            close=50355.0
        ),

        # Even if other factors are good...
        market_profile_15m=MockMarketProfile(
            value_area_high=50500.0,
            value_area_low=50350.0,  # At VAL
            point_of_control=50400.0
        ),

        price_mean_15m=50500.0,
        price_std_dev_15m=50.0,
        price_autocorrelation=0.2,
        demand_zones=[MockZone(price_low=50340.0, price_high=50360.0, is_fresh=True)],
        supply_zones=[],
        fair_value_gaps=[]
    )


async def test_scenario(name: str, market_data: MockMarketData, expected_result: str):
    """Test a single scenario."""
    print(f"\n{'='*80}")
    print(f"TEST: {name}")
    print(f"{'='*80}")

    # Create decision engine
    engine = create_default_decision_engine(min_confluence=3.0)

    # Register signal callback
    signals_generated = []

    async def on_signal(signal: TradeSignal):
        signals_generated.append(signal)

    engine.on_signal_generated(on_signal)

    # Evaluate
    print(f"\nMarket Data:")
    print(f"  Symbol: {market_data.symbol}")
    print(f"  Price: ${market_data.current_price:,.2f}")
    print(f"  Buy/Sell Volume: {market_data.buy_volume_30s:,.0f} / {market_data.sell_volume_30s:,.0f}")

    signal = await engine.evaluate(market_data)

    # Check result
    print(f"\n{'='*80}")
    if signal:
        print(f"✅ SIGNAL GENERATED")
        print(f"  Side: {signal.side.upper()}")
        print(f"  Confluence: {signal.confluence_score:.1f}/{engine.max_possible_score:.1f} ({signal.confluence_score/engine.max_possible_score*100:.0f}%)")
        print(f"  Confidence: {signal.confidence.upper()}")
        print(f"\n  Primary Signals:")
        for ps in signal.primary_signals:
            print(f"    • {ps.reason}")
        print(f"\n  Filter Contributions:")
        for name, score in sorted(signal.filter_scores.items(), key=lambda x: x[1], reverse=True):
            if score > 0:
                print(f"    • {name}: +{score:.2f} points")
    else:
        print(f"❌ NO SIGNAL GENERATED")
        print(f"  Result: Signal rejected (see logs above for reason)")

    print(f"{'='*80}\n")

    # Verify expectation
    if expected_result == 'SIGNAL' and signal:
        print(f"✅ Test passed: Signal generated as expected\n")
        return True
    elif expected_result == 'REJECT' and not signal:
        print(f"✅ Test passed: Signal rejected as expected\n")
        return True
    else:
        print(f"❌ Test failed: Expected {expected_result}, got {'SIGNAL' if signal else 'REJECT'}\n")
        return False


async def main():
    """Run all test scenarios."""
    print("\n" + "="*80)
    print("DECISION ENGINE TEST SUITE")
    print("="*80)
    print("\nTesting signal generation with various market scenarios...")

    results = []

    # Test 1: Strong bullish signal
    results.append(await test_scenario(
        "Strong Bullish Signal (High Confluence)",
        create_strong_bullish_signal(),
        'SIGNAL'
    ))

    await asyncio.sleep(0.1)

    # Test 2: Weak signal (should be rejected)
    results.append(await test_scenario(
        "Weak Signal (Low Confluence - Should Reject)",
        create_weak_signal(),
        'REJECT'
    ))

    await asyncio.sleep(0.1)

    # Test 3: Failed primary signals
    results.append(await test_scenario(
        "Failed Primary Signals (Should Reject)",
        create_failed_primary(),
        'REJECT'
    ))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    passed = sum(results)
    total = len(results)
    print(f"\nTests passed: {passed}/{total}")

    if passed == total:
        print("✅ All tests passed!")
    else:
        print(f"❌ {total - passed} test(s) failed")

    print("\n" + "="*80)


if __name__ == '__main__':
    asyncio.run(main())
