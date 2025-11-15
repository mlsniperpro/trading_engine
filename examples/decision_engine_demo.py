"""
Decision Engine Integration Demo

Demonstrates how to:
1. Create and configure the decision engine
2. Connect to analytics events
3. Handle trading signals
4. Customize analyzers and filters
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from decision import (
    create_default_decision_engine,
    DecisionEngine,
    OrderFlowAnalyzer,
    MicrostructureAnalyzer,
    MarketProfileFilter,
    MeanReversionFilter,
    AutocorrelationFilter,
    DemandZoneFilter,
    SupplyZoneFilter,
    FairValueGapFilter,
    TradeSignal
)


async def demo_default_engine():
    """Demo 1: Using default engine configuration."""
    print("\n" + "="*80)
    print("DEMO 1: Default Decision Engine")
    print("="*80)

    # Create engine with default configuration
    engine = create_default_decision_engine(min_confluence=3.0)

    # Get stats
    stats = engine.get_stats()
    print(f"\nEngine Configuration:")
    print(f"  Min Confluence: {stats['min_confluence_score']:.1f}")
    print(f"  Max Score: {stats['max_possible_score']:.1f}")
    print(f"\n  Primary Analyzers ({len(stats['primary_analyzers'])}):")
    for analyzer in stats['primary_analyzers']:
        print(f"    • {analyzer}")
    print(f"\n  Secondary Filters ({len(stats['secondary_filters'])}):")
    for filter_info in stats['secondary_filters']:
        print(f"    • {filter_info['name']} (weight: {filter_info['weight']})")

    total_weight = sum(f['weight'] for f in stats['secondary_filters'])
    print(f"\n  Total Filter Weight: {total_weight:.1f} points")


async def demo_custom_engine():
    """Demo 2: Creating custom engine with different configuration."""
    print("\n" + "="*80)
    print("DEMO 2: Custom Decision Engine")
    print("="*80)

    # Create custom analyzers
    primary = [
        OrderFlowAnalyzer(threshold=3.0),  # More aggressive threshold
        MicrostructureAnalyzer(min_wick_ratio=1.5)  # Less strict rejection
    ]

    # Create custom filters with different weights
    secondary = [
        DemandZoneFilter(weight=3.0),  # Prioritize demand zones
        MarketProfileFilter(weight=2.0),
        MeanReversionFilter(weight=1.0),
        AutocorrelationFilter(weight=0.5),
    ]

    # Create engine
    engine = DecisionEngine(
        primary_analyzers=primary,
        secondary_filters=secondary,
        min_confluence_score=2.5,  # Lower threshold
        name="AggressiveEngine"
    )

    stats = engine.get_stats()
    print(f"\nCustom Engine: {stats['name']}")
    print(f"  Min Confluence: {stats['min_confluence_score']:.1f}")
    print(f"  Max Score: {stats['max_possible_score']:.1f}")
    print(f"  Strategy: Prioritize demand zones, aggressive entries")


async def demo_signal_handling():
    """Demo 3: Handling trading signals."""
    print("\n" + "="*80)
    print("DEMO 3: Signal Handling")
    print("="*80)

    engine = create_default_decision_engine(min_confluence=3.0)

    # Register signal callback
    async def on_trading_signal(signal: TradeSignal):
        """
        This callback is called when a trading signal is generated.

        In production, this would:
        1. Emit TradingSignalGenerated event to event bus
        2. Notify execution engine
        3. Send alerts via email/SMS
        4. Log to database
        """
        print(f"\n🎯 TRADING SIGNAL RECEIVED:")
        print(f"  Symbol: {signal.symbol}")
        print(f"  Side: {signal.side.upper()}")
        print(f"  Entry Price: ${signal.entry_price:,.2f}")
        print(f"  Confluence: {signal.confluence_score:.1f}/10.0")
        print(f"  Confidence: {signal.confidence.upper()}")
        print(f"  Timestamp: {signal.timestamp.isoformat()}")

        print(f"\n  Primary Signals:")
        for ps in signal.primary_signals:
            status = "✅" if ps.passed else "❌"
            print(f"    {status} {ps.reason}")

        print(f"\n  Filter Scores:")
        for name, score in sorted(signal.filter_scores.items(), key=lambda x: x[1], reverse=True):
            if score > 0:
                print(f"    • {name}: +{score:.2f}")

        # Convert to dict for event emission
        signal_dict = signal.to_dict()
        print(f"\n  Event Payload Ready:")
        print(f"    Keys: {list(signal_dict.keys())}")

    # Register callback
    engine.on_signal_generated(on_trading_signal)
    print(f"\n✅ Signal callback registered")
    print(f"Engine is now ready to receive analytics events and generate signals")


async def demo_analytics_integration():
    """Demo 4: Integration with analytics events."""
    print("\n" + "="*80)
    print("DEMO 4: Analytics Event Integration")
    print("="*80)

    engine = create_default_decision_engine(min_confluence=3.0)

    # Example: Subscribing to analytics events
    print(f"\nIn production, you would:")
    print(f"  1. Get EventBus instance from dependency injection")
    print(f"  2. Subscribe DecisionEngine to analytics events:")
    print(f"\n  ```python")
    print(f"  # Subscribe to analytics completed events")
    print(f"  event_bus.subscribe(")
    print(f"      event_type='AnalyticsCompleted',")
    print(f"      handler=engine.on_analytics_event")
    print(f"  )")
    print(f"  ```")
    print(f"\n  3. Analytics engine emits events when analysis completes")
    print(f"  4. DecisionEngine receives events and evaluates signals")
    print(f"  5. If signal generated, DecisionEngine emits TradingSignalGenerated")
    print(f"  6. Execution engine subscribes to TradingSignalGenerated")

    # Simulate analytics event
    print(f"\n  Example event flow:")
    print(f"    Analytics → [AnalyticsCompleted] → DecisionEngine")
    print(f"    DecisionEngine → [TradingSignalGenerated] → ExecutionEngine")
    print(f"    ExecutionEngine → [OrderPlaced] → Exchange")


async def demo_confluence_thresholds():
    """Demo 5: Understanding confluence thresholds."""
    print("\n" + "="*80)
    print("DEMO 5: Confluence Thresholds")
    print("="*80)

    print(f"\nConfluence Score Interpretation:")
    print(f"  MAX POSSIBLE: 8.0 points (with default filters)")
    print(f"\n  Score Ranges:")
    print(f"    • >= 7.0 (87%+) → VERY HIGH confidence")
    print(f"    • >= 5.0 (62%+) → HIGH confidence")
    print(f"    • >= 4.0 (50%+) → MEDIUM confidence")
    print(f"    • >= 3.0 (37%+) → LOW confidence (minimum threshold)")
    print(f"    • <  3.0 (<37%) → REJECTED (insufficient confluence)")

    print(f"\n  Example Scenarios:")
    print(f"\n  1. Score 7.5/8.0 (94%) - VERY HIGH:")
    print(f"     • All primary signals pass")
    print(f"     • 5/6 filters contribute")
    print(f"     • Strong reversal setup at demand zone")
    print(f"     → Highest probability trade")

    print(f"\n  2. Score 4.2/8.0 (52%) - MEDIUM:")
    print(f"     • All primary signals pass")
    print(f"     • 2-3 filters contribute")
    print(f"     • Decent setup but not ideal")
    print(f"     → Moderate probability trade")

    print(f"\n  3. Score 2.5/8.0 (31%) - REJECTED:")
    print(f"     • Primary signals pass")
    print(f"     • Only 1 filter contributes")
    print(f"     • Weak setup, poor risk/reward")
    print(f"     → NO TRADE")


async def main():
    """Run all demos."""
    print("\n" + "="*80)
    print("DECISION ENGINE INTEGRATION DEMO")
    print("="*80)
    print("\nThis demo shows how to integrate the decision engine")
    print("into your algorithmic trading system.")

    await demo_default_engine()
    await demo_custom_engine()
    await demo_signal_handling()
    await demo_analytics_integration()
    await demo_confluence_thresholds()

    print("\n" + "="*80)
    print("DEMO COMPLETE")
    print("="*80)
    print("\nNext Steps:")
    print("  1. Run tests: python tests/test_decision_engine.py")
    print("  2. Integrate with analytics engine")
    print("  3. Connect to event bus")
    print("  4. Implement signal handlers in execution engine")
    print("\n" + "="*80 + "\n")


if __name__ == '__main__':
    asyncio.run(main())
