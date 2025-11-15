"""
SECONDARY FILTER #3: Autocorrelation Filter (Weight: 1.0)

Analyzes price serial correlation to predict regime.
High correlation = trending, Low correlation = mean-reverting.

Autocorrelation measures how much current price depends on past prices.
"""

from typing import Any
import logging

from decision.filters.base import SignalFilter

logger = logging.getLogger(__name__)


class AutocorrelationFilter(SignalFilter):
    """
    FILTER #3: Autocorrelation analysis (weight: 1.0)

    Scoring Logic:
    - |r| > 0.6: +1.0 point (strong trend - momentum trades work)
    - |r| < 0.3: +1.0 point (low correlation - mean reversion works)
    - 0.3 <= |r| <= 0.6: +0.5 points (moderate - mixed regime)

    Key Insight:
    Market regime determines strategy effectiveness:
    - High autocorrelation (r > 0.6): Trending - use breakout strategies
    - Low autocorrelation (r < 0.3): Mean-reverting - use reversion strategies
    - Middle range: Mixed regime - lower confidence

    Returns autocorrelation coefficient r: [-1, 1]
    r > 0: Positive correlation (trending)
    r < 0: Negative correlation (oscillating)
    r ≈ 0: No correlation (random walk)
    """

    def __init__(self, weight: float = 1.0, strong_threshold: float = 0.6, weak_threshold: float = 0.3):
        """
        Initialize autocorrelation filter.

        Args:
            weight: Filter weight (default: 1.0)
            strong_threshold: Threshold for strong correlation (default: 0.6)
            weak_threshold: Threshold for weak correlation (default: 0.3)
        """
        super().__init__(weight)
        self.strong_threshold = strong_threshold
        self.weak_threshold = weak_threshold
        self.logger.info(
            f"AutocorrelationFilter initialized (weight={weight}, "
            f"strong={strong_threshold}, weak={weak_threshold})"
        )

    async def evaluate(self, market_data: Any) -> float:
        """
        Evaluate autocorrelation regime.

        Expected market_data attributes:
        - price_autocorrelation: Autocorrelation coefficient r

        Returns:
            Score from 0.0 to 1.0
        """
        try:
            # Extract data
            correlation = getattr(market_data, 'price_autocorrelation', None)

            if correlation is None:
                self.log_score(0.0, "- No autocorrelation data")
                return 0.0

            correlation = float(correlation)
            abs_corr = abs(correlation)

            # Scoring logic
            if abs_corr > self.strong_threshold:
                score = self.weight  # Full points - strong trend
                regime = "strong trend" if correlation > 0 else "strong oscillation"
                self.log_score(
                    score,
                    f"- {regime}: r={correlation:.2f} (|r|>{self.strong_threshold})"
                )
            elif abs_corr < self.weak_threshold:
                score = self.weight  # Full points - mean reverting
                self.log_score(
                    score,
                    f"- Mean reverting regime: r={correlation:.2f} (|r|<{self.weak_threshold})"
                )
            else:
                score = self.weight * 0.5  # Partial points - mixed regime
                self.log_score(
                    score,
                    f"- Mixed regime: r={correlation:.2f} "
                    f"({self.weak_threshold}<=|r|<={self.strong_threshold})"
                )

            return score

        except Exception as e:
            self.logger.error(f"Error in autocorrelation evaluation: {e}")
            return 0.0
