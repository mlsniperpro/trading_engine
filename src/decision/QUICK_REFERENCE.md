# Decision Engine - Quick Reference

## Quick Start

```python
from decision import create_default_decision_engine

# Create engine
engine = create_default_decision_engine(min_confluence=3.0)

# Register callback
async def on_signal(signal):
    print(f"Signal: {signal.symbol} {signal.side} @ {signal.confluence_score:.1f}")

engine.on_signal_generated(on_signal)

# Evaluate
signal = await engine.evaluate(market_data)
```

## Components at a Glance

### Primary Analyzers (ALL must pass)

| Analyzer | Threshold | Pass Condition |
|----------|-----------|----------------|
| OrderFlowAnalyzer | 2.5:1 ratio | Buy/Sell > 2.5 or Sell/Buy > 2.5 |
| MicrostructureAnalyzer | 2x body | Wick > 2x body, close @80% |

### Secondary Filters (Weighted Scoring)

| Filter | Weight | Full Score Condition |
|--------|--------|---------------------|
| MarketProfileFilter | 1.5 | At VAH/VAL extremes |
| MeanReversionFilter | 1.5 | Beyond 2σ from mean |
| AutocorrelationFilter | 1.0 | Strong trend or mean-reverting |
| DemandZoneFilter | 2.0 | Fresh untested zone |
| SupplyZoneFilter | 0.5 | Target zone above price |
| FairValueGapFilter | 1.5 | Unfilled gap at price |

**Total**: 8.0 points

## Confluence Thresholds

| Score | Confidence | Action |
|-------|------------|--------|
| >= 7.0 | VERY HIGH | Best trades |
| >= 5.0 | HIGH | Good trades |
| >= 4.0 | MEDIUM | Acceptable |
| >= 3.0 | LOW | Minimum |
| < 3.0 | INSUFFICIENT | REJECT |

## Market Data Requirements

```python
@dataclass
class MarketData:
    # Basic
    symbol: str
    current_price: float

    # Order flow
    buy_volume_30s: float
    sell_volume_30s: float

    # Microstructure
    latest_candle_1m: Candle  # open, high, low, close

    # Market profile
    market_profile_15m: Profile  # vah, val, poc

    # Mean reversion
    price_mean_15m: float
    price_std_dev_15m: float

    # Autocorrelation
    price_autocorrelation: float  # -1 to 1

    # Zones
    demand_zones: List[Zone]  # price_low, price_high, is_fresh, test_count
    supply_zones: List[Zone]

    # FVGs
    fair_value_gaps: List[FVG]  # gap_low, gap_high, is_filled, direction
```

## Signal Flow

```
Analytics → AnalyticsCompleted Event
    ↓
DecisionEngine.on_analytics_event()
    ↓
Run Primary Analyzers → All pass?
    ↓ YES
Run Secondary Filters → Calculate scores
    ↓
Calculate Confluence → Score >= 3.0?
    ↓ YES
Generate TradeSignal
    ↓
Emit TradingSignalGenerated Event
    ↓
Execution Engine
```

## Common Use Cases

### Default Configuration
```python
engine = create_default_decision_engine(min_confluence=3.0)
```

### Conservative (High Quality)
```python
engine = create_default_decision_engine(min_confluence=5.0)
```

### Aggressive (More Signals)
```python
engine = DecisionEngine(
    primary_analyzers=[OrderFlowAnalyzer(threshold=2.0)],
    secondary_filters=[...],
    min_confluence_score=2.0
)
```

### Zone-Focused
```python
filters = [
    DemandZoneFilter(weight=4.0),  # Prioritize
    MarketProfileFilter(weight=2.0),
    # ... rest
]
```

## Debugging

```python
# Get engine stats
stats = engine.get_stats()
print(stats)

# Check primary results
for result in signal.primary_signals:
    print(f"{result.passed}: {result.reason}")

# Check filter contributions
for name, score in signal.filter_scores.items():
    print(f"{name}: {score:.2f}")
```

## Testing

```bash
# Run test suite
python tests/test_decision_engine.py

# Run demo
python examples/decision_engine_demo.py
```

## Typical Signal Example

```
STRONG BULLISH SIGNAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Symbol: BTCUSDT
Price: $50,250.00
Side: LONG
Confluence: 7.5/8.0 (94%)
Confidence: VERY HIGH

PRIMARY SIGNALS:
✅ OrderFlow: 3.5:1 buy/sell ratio
✅ Microstructure: Bullish rejection

SECONDARY FILTERS:
• DemandZone: +2.0 (fresh zone)
• MarketProfile: +1.5 (at VAL)
• MeanReversion: +1.5 (beyond 2σ)
• FVG: +1.5 (unfilled gap)
• Autocorrelation: +1.0 (mean reverting)
• SupplyZone: +0.0 (no target)

DECISION: ✅ ENTER LONG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Key Files

| File | Purpose |
|------|---------|
| `engine.py` | Main DecisionEngine class |
| `signal_pipeline.py` | SignalResult, TradeSignal data structures |
| `confluence.py` | Score aggregation |
| `analyzers/order_flow_analyzer.py` | PRIMARY #1: Order flow |
| `analyzers/microstructure_analyzer.py` | PRIMARY #2: Rejections |
| `filters/demand_zone_filter.py` | FILTER #4: Demand zones (2.0) |
| `filters/market_profile_filter.py` | FILTER #1: Profile (1.5) |

## Performance Tips

1. **Early exit**: Primary analyzers stop on first failure
2. **Async**: All methods are async for non-blocking I/O
3. **Stateless**: No internal state, pure functions
4. **Lightweight**: Minimal memory per evaluation

## Common Patterns

### Event Integration
```python
event_bus.subscribe('AnalyticsCompleted', engine.on_analytics_event)
```

### Signal Callback
```python
async def handle_signal(signal):
    await event_bus.publish('TradingSignalGenerated', signal.to_dict())

engine.on_signal_generated(handle_signal)
```

### Custom Analyzer
```python
class MyAnalyzer(SignalAnalyzer):
    async def analyze(self, market_data):
        return SignalResult(
            passed=True,
            strength=0.8,
            reason="Custom logic",
            direction='long'
        )
```

### Custom Filter
```python
class MyFilter(SignalFilter):
    async def evaluate(self, market_data):
        score = self.weight if condition else 0.0
        self.log_score(score, "reason")
        return score
```
