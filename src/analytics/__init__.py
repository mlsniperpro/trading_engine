"""
Analytics Engine - Real-time market data analytics.

Components:
- AnalyticsEngine: 24/7 coordinator for all analytics
- OrderFlowAnalyzer: CVD, imbalances, whale detection
- MarketProfileAnalyzer: POC, VAH, VAL calculations
- MicrostructureAnalyzer: Rejection patterns, candle strength
- TechnicalIndicators: RSI, EMA, VWAP, etc.
- SupplyDemandDetector: Zone identification and tracking
- FairValueGapDetector: FVG detection and fill tracking
- MultiTimeframeManager: Cross-timeframe coordination
"""

from .engine import AnalyticsEngine, AnalyticsSnapshot
from .order_flow import OrderFlowAnalyzer, TradeTick, CVDResult, ImbalanceResult
from .market_profile import MarketProfileAnalyzer, PriceLevel, MarketProfile
from .microstructure import MicrostructureAnalyzer, Candle, RejectionPattern
from .supply_demand import SupplyDemandDetector, Zone, ZoneStatus
from .fair_value_gap import FairValueGapDetector, FairValueGap, FVGType, FVGStatus
from .multi_timeframe import MultiTimeframeManager, TimeframeCandle, TrendDirection
from . import indicators

__all__ = [
    # Main engine
    'AnalyticsEngine',
    'AnalyticsSnapshot',

    # Order flow
    'OrderFlowAnalyzer',
    'TradeTick',
    'CVDResult',
    'ImbalanceResult',

    # Market profile
    'MarketProfileAnalyzer',
    'PriceLevel',
    'MarketProfile',

    # Microstructure
    'MicrostructureAnalyzer',
    'Candle',
    'RejectionPattern',

    # Indicators
    'indicators',

    # Supply/Demand
    'SupplyDemandDetector',
    'Zone',
    'ZoneStatus',

    # Fair Value Gaps
    'FairValueGapDetector',
    'FairValueGap',
    'FVGType',
    'FVGStatus',

    # Multi-timeframe
    'MultiTimeframeManager',
    'TimeframeCandle',
    'TrendDirection',
]
