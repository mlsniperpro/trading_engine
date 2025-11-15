# Decision Engine

The Decision Engine is the core signal generation component of the trading system. It uses a hierarchical two-stage analysis system with composition-based design patterns to generate high-probability trading signals.

## Architecture

### Design Pattern: Composition + Event-Driven

```
┌─────────────────────────────────────────────────────────────┐
│                      DECISION ENGINE                         │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  STAGE 1: PRIMARY ANALYZERS (ALL must pass)        │    │
│  │  • OrderFlowAnalyzer         (2.5:1 threshold)     │    │
│  │  • MicrostructureAnalyzer    (rejection patterns)  │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│                   All Pass? ✅                               │
│                         ↓                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │  STAGE 2: SECONDARY FILTERS (Weighted scoring)     │    │
│  │  • MarketProfileFilter        (+1.5 points)        │    │
│  │  • MeanReversionFilter        (+1.5 points)        │    │
│  │  • AutocorrelationFilter      (+1.0 point)         │    │
│  │  • DemandZoneFilter           (+2.0 points)        │    │
│  │  • SupplyZoneFilter           (+0.5 points)        │    │
│  │  • FairValueGapFilter         (+1.5 points)        │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│                 Confluence >= 3.0? ✅                        │
│                         ↓                                    │
│              🎯 TRADING SIGNAL GENERATED                     │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. DecisionEngine (`engine.py`)

Main orchestrator that composes analyzers and filters.

```python
from decision import create_default_decision_engine

# Create engine with default configuration
engine = create_default_decision_engine(min_confluence=3.0)

# Register signal callback
async def on_signal(signal):
    print(f"Signal: {signal.symbol} {signal.side} @ {signal.confluence_score:.1f}")

engine.on_signal_generated(on_signal)

# Evaluate market data
signal = await engine.evaluate(market_data)
```

### 2. Primary Analyzers (`analyzers/`)

**Entry triggers - ALL must pass for signal generation**

#### OrderFlowAnalyzer
- Detects aggressive buy/sell pressure
- Threshold: >2.5:1 ratio (configurable)
- Returns: Pass/Fail + Direction (long/short)

```python
from decision.analyzers import OrderFlowAnalyzer

analyzer = OrderFlowAnalyzer(threshold=2.5)
result = await analyzer.analyze(market_data)
# result.passed = True/False
# result.direction = 'long' or 'short'
```

#### MicrostructureAnalyzer
- Detects price rejection patterns (pin bars)
- Pattern: Wick >2x body size, close in upper/lower 80%
- Returns: Pass/Fail + Direction

```python
from decision.analyzers import MicrostructureAnalyzer

analyzer = MicrostructureAnalyzer(min_wick_ratio=2.0)
result = await analyzer.analyze(market_data)
```

### 3. Secondary Filters (`filters/`)

**Confirmation - Weighted scoring (don't block signals)**

#### MarketProfileFilter (Weight: 1.5)
- At VAH/VAL extremes: +1.5 points (full)
- Inside value area: +0.5 points (33%)
- Outside value area: 0 points

#### MeanReversionFilter (Weight: 1.5)
- Beyond 2σ from mean: +1.5 points (full)
- Beyond 1σ from mean: +0.75 points (50%)
- Inside 1σ: 0 points

#### AutocorrelationFilter (Weight: 1.0)
- High correlation |r| > 0.6: +1.0 point (trending)
- Low correlation |r| < 0.3: +1.0 point (mean reverting)
- Moderate: +0.5 points (mixed)

#### DemandZoneFilter (Weight: 2.0)
- Fresh demand zone: +2.0 points (full)
- Tested zone (1-2x): +1.0 point (50%)
- Over-tested: 0 points

#### SupplyZoneFilter (Weight: 0.5)
- Supply zone above price: +0.5 points (target exists)
- No zone above: 0 points

#### FairValueGapFilter (Weight: 1.5)
- Unfilled FVG at price: +1.5 points (full)
- Partially filled: +0.75 points (50%)
- Filled or none: 0 points

### 4. Confluence Calculator (`confluence.py`)

Aggregates scores and determines signal confidence.

```python
from decision.confluence import ConfluenceCalculator

calculator = ConfluenceCalculator()
result = await calculator.calculate(
    primary_results=primary_results,
    filter_scores=filter_scores,
    max_possible_score=10.0
)

print(f"Score: {result.score:.1f}/{result.max_possible:.1f}")
print(f"Direction: {result.primary_direction}")
```

### 5. Data Structures (`signal_pipeline.py`)

#### SignalResult
Result from primary analyzers.

```python
@dataclass
class SignalResult:
    passed: bool
    strength: float      # 0.0 to 1.0
    reason: str
    direction: str       # 'long' or 'short'
    metadata: Dict
```

#### TradeSignal
Final trading signal with full context.

```python
@dataclass
class TradeSignal:
    symbol: str
    side: str            # 'long' or 'short'
    confluence_score: float
    primary_signals: List[SignalResult]
    filter_scores: Dict[str, float]
    timestamp: datetime
    entry_price: float
    confidence: str      # 'low', 'medium', 'high', 'very_high'
```

## Signal Generation Logic

### Two-Stage Hierarchy

**STAGE 1: PRIMARY SIGNALS (ALL must pass)**
- Check OrderFlowAnalyzer
- Check MicrostructureAnalyzer
- Verify directional agreement
- **IF ANY FAIL → REJECT immediately**

**STAGE 2: SECONDARY FILTERS (Weighted scoring)**
- Run all filters
- Sum weighted scores
- Calculate confluence
- **IF score < threshold → REJECT**

**STAGE 3: SIGNAL GENERATION**
- Create TradeSignal
- Assign confidence level
- Emit TradingSignalGenerated event

### Confluence Thresholds

```
Score Range          Confidence    Action
───────────────────────────────────────────
>= 7.0 (87%+)       VERY HIGH     Best trades
>= 5.0 (62%+)       HIGH          Good trades
>= 4.0 (50%+)       MEDIUM        Acceptable
>= 3.0 (37%+)       LOW           Minimum threshold
<  3.0 (<37%)       INSUFFICIENT  REJECT
```

### Example Scenarios

#### 1. Strong Bullish Signal (Score: 7.5/8.0)

```
PRIMARY SIGNALS:
✅ Order Flow: 3.5:1 buy/sell ratio
✅ Microstructure: Bullish rejection at $50,200

SECONDARY FILTERS:
✅ Market Profile: At VAL ($50,250)          +1.5
✅ Mean Reversion: -2.1σ from mean           +1.5
✅ Autocorrelation: r=0.2 (mean reverting)   +1.0
✅ Demand Zone: Fresh zone at price          +2.0
❌ Supply Zone: No target above              +0.0
✅ FVG: Unfilled bullish gap                 +1.5

CONFLUENCE: 7.5/8.0 (94%) → VERY HIGH
DECISION: ✅ ENTER LONG
```

#### 2. Weak Signal - Rejected (Score: 1.0/8.0)

```
PRIMARY SIGNALS:
✅ Order Flow: 2.8:1 buy/sell ratio (barely passes)
✅ Microstructure: Small rejection pattern

SECONDARY FILTERS:
⚠️  Market Profile: Inside value area        +0.5
❌ Mean Reversion: Only 0.2σ away            +0.0
⚠️  Autocorrelation: r=0.45 (moderate)       +0.5
❌ Demand Zone: No zone at price             +0.0
❌ Supply Zone: No target                    +0.0
❌ FVG: Gap already filled                   +0.0

CONFLUENCE: 1.0/8.0 (12.5%) → INSUFFICIENT
DECISION: ❌ REJECT (need 3.0 minimum)
```

#### 3. Failed Primary - Rejected

```
PRIMARY SIGNALS:
❌ Order Flow: 1.5:1 ratio (below 2.5 threshold)
❌ Microstructure: No rejection pattern

DECISION: ❌ REJECT IMMEDIATELY (primary failed)
Note: Secondary filters not evaluated (early exit)
```

## Usage Examples

### Basic Usage

```python
from decision import create_default_decision_engine

# Create engine
engine = create_default_decision_engine(min_confluence=3.0)

# Evaluate market data
signal = await engine.evaluate(market_data)

if signal:
    print(f"Signal: {signal.side} @ {signal.confluence_score:.1f}")
```

### Custom Configuration

```python
from decision import DecisionEngine, OrderFlowAnalyzer, DemandZoneFilter

# Create custom analyzers
primary = [
    OrderFlowAnalyzer(threshold=3.0),  # More aggressive
]

# Create custom filters
secondary = [
    DemandZoneFilter(weight=3.0),  # Prioritize zones
]

# Create engine
engine = DecisionEngine(
    primary_analyzers=primary,
    secondary_filters=secondary,
    min_confluence_score=2.5
)
```

### Event Integration

```python
# Subscribe to analytics events
event_bus.subscribe(
    event_type='AnalyticsCompleted',
    handler=engine.on_analytics_event
)

# Register signal callback
async def on_signal(signal):
    # Emit to execution engine
    await event_bus.publish('TradingSignalGenerated', signal.to_dict())

engine.on_signal_generated(on_signal)
```

## Testing

Run the test suite:

```bash
python tests/test_decision_engine.py
```

Run the demo:

```bash
python examples/decision_engine_demo.py
```

## Extension Points

### Adding New Analyzers

```python
from decision.analyzers.base import SignalAnalyzer
from decision.signal_pipeline import SignalResult

class VolumeAnalyzer(SignalAnalyzer):
    async def analyze(self, market_data):
        # Your logic here
        return SignalResult(
            passed=True,
            strength=0.8,
            reason="High volume breakout",
            direction='long',
            metadata={}
        )
```

### Adding New Filters

```python
from decision.filters.base import SignalFilter

class LiquidityFilter(SignalFilter):
    def __init__(self, weight: float = 1.0):
        super().__init__(weight)

    async def evaluate(self, market_data):
        # Your scoring logic
        score = self.weight if condition else 0.0
        self.log_score(score, "reason")
        return score
```

## Performance Considerations

- **Early Exit**: Primary analyzers exit immediately on first failure
- **Async Design**: All analyzers/filters are async for parallel execution
- **Stateless**: No internal state, pure functions
- **Lightweight**: Minimal memory footprint per evaluation

## Integration Checklist

- [ ] Create DecisionEngine instance
- [ ] Subscribe to analytics events
- [ ] Register signal callbacks
- [ ] Connect to event bus
- [ ] Test with mock data
- [ ] Monitor confluence scores
- [ ] Tune thresholds based on backtest results

## Resources

- Design Spec: `/design_spec/DESIGN_DOC (1).md`
- Test Suite: `/tests/test_decision_engine.py`
- Demo: `/examples/decision_engine_demo.py`
- Architecture: `/design_spec/TECHNICAL_ARCHITECTURE.md`
