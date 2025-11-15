"""
Decision Engine - Core signal generation orchestrator.

Reactive component that:
1. Subscribes to analytics events
2. Runs primary analyzers (ALL must pass)
3. Runs secondary filters (weighted scoring)
4. Emits TradingSignalGenerated if confluence >= threshold

Design Pattern: Event-driven composition
- Subscribes to analytics events (reactive)
- Composes multiple analyzers and filters
- Emits trading signals when conditions met
"""

from typing import List, Optional, Any, Callable
from datetime import datetime
import logging

from decision.analyzers.base import SignalAnalyzer
from decision.filters.base import SignalFilter
from decision.signal_pipeline import SignalResult, TradeSignal
from decision.confluence import ConfluenceCalculator, ConfluenceResult

logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Main decision engine that orchestrates signal generation.

    Composition Design:
    - Primary analyzers: ALL must pass (entry triggers)
    - Secondary filters: Weighted scoring (confirmation)
    - Confluence calculator: Aggregates scores
    - Event emitter: Publishes trading signals

    Workflow:
    1. Receive analytics event (market data)
    2. Run primary analyzers -> if ANY fail, stop
    3. Run secondary filters -> calculate scores
    4. Calculate confluence -> if >= threshold, emit signal
    5. Emit TradingSignalGenerated event
    """

    def __init__(
        self,
        primary_analyzers: List[SignalAnalyzer],
        secondary_filters: List[SignalFilter],
        min_confluence_score: float = 3.0,
        name: str = "DecisionEngine"
    ):
        """
        Initialize decision engine.

        Args:
            primary_analyzers: List of primary signal analyzers (ALL must pass)
            secondary_filters: List of secondary filters (weighted scoring)
            min_confluence_score: Minimum confluence score for signal (default: 3.0)
            name: Engine name for logging
        """
        self.primary_analyzers = primary_analyzers
        self.secondary_filters = secondary_filters
        self.min_confluence_score = min_confluence_score
        self.name = name

        # Calculate max possible score
        self.max_possible_score = sum(f.weight for f in secondary_filters)

        # Confluence calculator
        self.confluence_calculator = ConfluenceCalculator()

        # Event callbacks
        self._signal_callbacks: List[Callable] = []

        # Logging
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self.logger.info(
            f"DecisionEngine initialized: "
            f"{len(primary_analyzers)} primary analyzers, "
            f"{len(secondary_filters)} secondary filters, "
            f"min_confluence={min_confluence_score:.1f}/{self.max_possible_score:.1f}"
        )

    async def evaluate(self, market_data: Any) -> Optional[TradeSignal]:
        """
        Evaluate market data and generate trade signal if conditions met.

        This is the core decision logic:
        1. Run ALL primary analyzers (must all pass)
        2. Run secondary filters (calculate scores)
        3. Calculate confluence score
        4. Generate signal if score >= threshold

        Args:
            market_data: Market data object with tick data, analytics results, etc.

        Returns:
            TradeSignal if conditions met, None otherwise
        """
        try:
            symbol = getattr(market_data, 'symbol', 'UNKNOWN')
            current_price = getattr(market_data, 'current_price', None)

            self.logger.debug(f"Evaluating market data for {symbol}")

            # Step 1: Run primary analyzers (ALL must pass)
            primary_results = []
            for analyzer in self.primary_analyzers:
                result = await analyzer.analyze(market_data)
                primary_results.append(result)

                if not result.passed:
                    self.logger.debug(
                        f"❌ Primary signal failed: {analyzer.name} - {result.reason}"
                    )
                    return None  # Early exit on first failure

            self.logger.info(
                f"✅ All {len(primary_results)} primary signals passed for {symbol}"
            )

            # Step 2: Run secondary filters (calculate scores)
            filter_scores = {}
            for filter_obj in self.secondary_filters:
                score = await filter_obj.evaluate(market_data)
                filter_scores[filter_obj.name] = score

            # Step 3: Calculate confluence
            confluence_result = await self.confluence_calculator.calculate(
                primary_results=primary_results,
                filter_scores=filter_scores,
                max_possible_score=self.max_possible_score
            )

            # Check if primary analyzers agree on direction
            if not confluence_result.primary_passed or not confluence_result.primary_direction:
                self.logger.warning("Primary analyzers passed but no valid direction")
                return None

            # Step 4: Check confluence threshold
            if confluence_result.score < self.min_confluence_score:
                self.logger.info(
                    f"⚠️  Insufficient confluence: {confluence_result.score:.1f} < "
                    f"{self.min_confluence_score:.1f} (need {self.min_confluence_score - confluence_result.score:.1f} more points)"
                )
                return None

            # Step 5: Generate trade signal
            confidence = self.confluence_calculator.get_confidence_level(
                confluence_result.score,
                self.max_possible_score
            )

            signal = TradeSignal(
                symbol=symbol,
                side=confluence_result.primary_direction,
                confluence_score=confluence_result.score,
                primary_signals=primary_results,
                filter_scores=filter_scores,
                timestamp=datetime.now(),
                entry_price=current_price,
                confidence=confidence
            )

            self.logger.info(
                f"🎯 TRADE SIGNAL GENERATED: {signal.symbol} {signal.side.upper()} | "
                f"Confluence: {signal.confluence_score:.1f}/{self.max_possible_score:.1f} | "
                f"Confidence: {signal.confidence.upper()}"
            )

            # Emit signal event
            await self._emit_signal(signal)

            return signal

        except Exception as e:
            self.logger.error(f"Error in decision engine evaluation: {e}")
            self.logger.exception("Full traceback:")
            return None

    async def on_analytics_event(self, event_data: Any) -> None:
        """
        Event handler for analytics events.

        This is called when analytics component publishes new analysis results.
        Reactive design: DecisionEngine subscribes to analytics events.

        Args:
            event_data: Event data from analytics (contains market_data)
        """
        try:
            self.logger.debug(f"Received analytics event: {type(event_data)}")

            # Extract market data from event
            # The event structure depends on your event system implementation
            # This is a generic handler that works with various formats

            if hasattr(event_data, 'market_data'):
                market_data = event_data.market_data
            elif hasattr(event_data, 'data'):
                market_data = event_data.data
            elif isinstance(event_data, dict) and 'market_data' in event_data:
                market_data = event_data['market_data']
            else:
                # Assume event_data is the market_data itself
                market_data = event_data

            # Evaluate market data
            signal = await self.evaluate(market_data)

            if signal:
                self.logger.info(f"Signal generated from analytics event: {signal}")

        except Exception as e:
            self.logger.error(f"Error handling analytics event: {e}")
            self.logger.exception("Full traceback:")

    def on_signal_generated(self, callback: Callable) -> None:
        """
        Register callback for signal generation events.

        Args:
            callback: Async function to call when signal is generated
                     Signature: async def callback(signal: TradeSignal) -> None
        """
        self._signal_callbacks.append(callback)
        self.logger.info(f"Registered signal callback: {callback.__name__}")

    async def _emit_signal(self, signal: TradeSignal) -> None:
        """
        Emit signal to all registered callbacks.

        Args:
            signal: Generated trade signal
        """
        for callback in self._signal_callbacks:
            try:
                await callback(signal)
            except Exception as e:
                self.logger.error(f"Error in signal callback {callback.__name__}: {e}")

    def get_stats(self) -> dict:
        """
        Get decision engine statistics.

        Returns:
            Dict with engine configuration and stats
        """
        return {
            'name': self.name,
            'primary_analyzers': [a.name for a in self.primary_analyzers],
            'secondary_filters': [
                {'name': f.name, 'weight': f.weight}
                for f in self.secondary_filters
            ],
            'min_confluence_score': self.min_confluence_score,
            'max_possible_score': self.max_possible_score,
            'signal_callbacks_registered': len(self._signal_callbacks)
        }


def create_default_decision_engine(
    min_confluence: float = 3.0
) -> DecisionEngine:
    """
    Factory function to create decision engine with default analyzers/filters.

    This is the standard configuration from the design spec:
    - PRIMARY: OrderFlowAnalyzer, MicrostructureAnalyzer
    - SECONDARY: 6 filters with weights totaling 10.0 points

    Args:
        min_confluence: Minimum confluence score (default: 3.0)

    Returns:
        Configured DecisionEngine instance
    """
    from decision.analyzers.order_flow_analyzer import OrderFlowAnalyzer
    from decision.analyzers.microstructure_analyzer import MicrostructureAnalyzer
    from decision.filters.market_profile_filter import MarketProfileFilter
    from decision.filters.mean_reversion_filter import MeanReversionFilter
    from decision.filters.autocorrelation_filter import AutocorrelationFilter
    from decision.filters.demand_zone_filter import DemandZoneFilter
    from decision.filters.supply_zone_filter import SupplyZoneFilter
    from decision.filters.fvg_filter import FairValueGapFilter

    # Primary analyzers (both must pass)
    primary_analyzers = [
        OrderFlowAnalyzer(threshold=2.5),
        MicrostructureAnalyzer()
    ]

    # Secondary filters (weighted scoring - total: 10.0 points)
    secondary_filters = [
        MarketProfileFilter(weight=1.5),      # 1.5 points
        MeanReversionFilter(weight=1.5),      # 1.5 points
        AutocorrelationFilter(weight=1.0),    # 1.0 point
        DemandZoneFilter(weight=2.0),         # 2.0 points
        SupplyZoneFilter(weight=0.5),         # 0.5 points
        FairValueGapFilter(weight=1.5),       # 1.5 points
        # Total: 8.0 points (can add more filters to reach 10.0)
    ]

    return DecisionEngine(
        primary_analyzers=primary_analyzers,
        secondary_filters=secondary_filters,
        min_confluence_score=min_confluence
    )
