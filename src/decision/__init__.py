"""
Decision Engine - Signal generation and trading logic.

This module implements the decision-making layer that:
1. Analyzes market data from analytics engine
2. Runs primary signal analyzers (ALL must pass)
3. Runs secondary filters (weighted confluence scoring)
4. Generates trade signals when confluence >= threshold

Design Pattern: Composition + Event-Driven
- Composes multiple analyzers and filters
- Reactive to analytics events
- Emits trading signal events

Components:
- DecisionEngine: Main orchestrator
- SignalAnalyzer: Base for primary analyzers (entry triggers)
- SignalFilter: Base for secondary filters (confirmation)
- ConfluenceCalculator: Score aggregation
- Signal data classes: SignalResult, TradeSignal
"""

from decision.engine import DecisionEngine, create_default_decision_engine
from decision.signal_pipeline import SignalResult, TradeSignal
from decision.confluence import ConfluenceCalculator, ConfluenceResult
from decision.analyzers.base import SignalAnalyzer
from decision.filters.base import SignalFilter

# Import concrete implementations
from decision.analyzers import (
    OrderFlowAnalyzer,
    MicrostructureAnalyzer
)
from decision.filters import (
    MarketProfileFilter,
    MeanReversionFilter,
    AutocorrelationFilter,
    DemandZoneFilter,
    SupplyZoneFilter,
    FairValueGapFilter
)

__all__ = [
    # Core engine
    'DecisionEngine',
    'create_default_decision_engine',

    # Data structures
    'SignalResult',
    'TradeSignal',
    'ConfluenceResult',

    # Base classes
    'SignalAnalyzer',
    'SignalFilter',
    'ConfluenceCalculator',

    # Primary analyzers
    'OrderFlowAnalyzer',
    'MicrostructureAnalyzer',

    # Secondary filters
    'MarketProfileFilter',
    'MeanReversionFilter',
    'AutocorrelationFilter',
    'DemandZoneFilter',
    'SupplyZoneFilter',
    'FairValueGapFilter'
]
