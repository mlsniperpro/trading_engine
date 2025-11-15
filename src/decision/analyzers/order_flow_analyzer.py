"""
PRIMARY SIGNAL #1: Order Flow Imbalance Analyzer

Detects aggressive buy/sell pressure from real trade data.
Entry trigger when buy/sell ratio exceeds threshold (default: 2.5:1)

This is a critical primary signal - it must pass for signal generation.
"""

from typing import Any
import logging

from decision.analyzers.base import SignalAnalyzer
from decision.signal_pipeline import SignalResult

logger = logging.getLogger(__name__)


class OrderFlowAnalyzer(SignalAnalyzer):
    """
    PRIMARY SIGNAL #1: Order flow imbalance detection.

    Analyzes real trade data to detect aggressive buying/selling pressure.
    Buy aggressor = trade at ask price (taker buys)
    Sell aggressor = trade at bid price (taker sells)

    Threshold Logic:
    - Buy/Sell ratio > threshold (default 2.5) = Bullish signal
    - Sell/Buy ratio > threshold = Bearish signal
    - Ratio <= threshold = No signal (balanced flow)

    Key Insight:
    Order flow shows REAL money moving, not fake walls.
    Aggressive takers reveal true supply/demand.
    """

    def __init__(self, threshold: float = 2.5, lookback_seconds: int = 30):
        """
        Initialize order flow analyzer.

        Args:
            threshold: Minimum buy/sell ratio for signal (default: 2.5)
            lookback_seconds: Time window for volume calculation (default: 30s)
        """
        super().__init__()
        self.threshold = threshold
        self.lookback_seconds = lookback_seconds
        self.logger.info(
            f"OrderFlowAnalyzer initialized (threshold={threshold}, "
            f"lookback={lookback_seconds}s)"
        )

    async def analyze(self, market_data: Any) -> SignalResult:
        """
        Analyze order flow imbalance.

        Expected market_data attributes:
        - buy_volume_30s: Aggressor buy volume (last 30 seconds)
        - sell_volume_30s: Aggressor sell volume (last 30 seconds)

        Returns:
            SignalResult with pass/fail and direction
        """
        try:
            # Extract volumes (handle different data structures)
            buy_volume = getattr(market_data, 'buy_volume_30s', 0.0)
            sell_volume = getattr(market_data, 'sell_volume_30s', 0.0)

            # Handle zero volumes
            if buy_volume == 0 and sell_volume == 0:
                return SignalResult(
                    passed=False,
                    strength=0.0,
                    reason="No volume data available",
                    direction=None,
                    metadata={'buy_volume': 0, 'sell_volume': 0, 'ratio': 0}
                )

            # Calculate ratios
            if sell_volume > 0:
                buy_ratio = buy_volume / sell_volume
            else:
                buy_ratio = float('inf') if buy_volume > 0 else 0

            if buy_volume > 0:
                sell_ratio = sell_volume / buy_volume
            else:
                sell_ratio = float('inf') if sell_volume > 0 else 0

            # Determine signal
            if buy_ratio > self.threshold:
                # Bullish signal
                passed = True
                direction = 'long'
                strength = min(buy_ratio / 5.0, 1.0)  # Normalize to 0-1
                reason = f"Bullish flow: {buy_ratio:.2f}:1 buy/sell ratio (>{self.threshold})"
            elif sell_ratio > self.threshold:
                # Bearish signal
                passed = True
                direction = 'short'
                strength = min(sell_ratio / 5.0, 1.0)
                reason = f"Bearish flow: {sell_ratio:.2f}:1 sell/buy ratio (>{self.threshold})"
            else:
                # Balanced flow - no signal
                passed = False
                direction = None
                strength = 0.0
                reason = f"Balanced flow: {max(buy_ratio, sell_ratio):.2f}:1 (<{self.threshold})"

            result = SignalResult(
                passed=passed,
                strength=strength,
                reason=reason,
                direction=direction,
                metadata={
                    'buy_volume': buy_volume,
                    'sell_volume': sell_volume,
                    'buy_ratio': buy_ratio,
                    'sell_ratio': sell_ratio,
                    'lookback_seconds': self.lookback_seconds
                }
            )

            self.log_result(result)
            return result

        except Exception as e:
            self.logger.error(f"Error in order flow analysis: {e}")
            return SignalResult(
                passed=False,
                strength=0.0,
                reason=f"Analysis error: {str(e)}",
                direction=None,
                metadata={}
            )
