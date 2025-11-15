"""
SECONDARY FILTER #2: Mean Reversion Filter (Weight: 1.5)

Detects extreme price deviations from recent mean.
Statistical extremes (>2σ) have high probability of reverting.

Uses 15-minute rolling price mean and standard deviation.
"""

from typing import Any
import logging

from decision.filters.base import SignalFilter

logger = logging.getLogger(__name__)


class MeanReversionFilter(SignalFilter):
    """
    FILTER #2: Mean reversion from recent price mean (weight: 1.5)

    Scoring Logic:
    - Beyond 2σ: +1.5 points (full weight) - extreme deviation
    - Beyond 1σ: +0.75 points (50% weight) - moderate deviation
    - Inside 1σ: 0 points - normal price range

    Key Insight:
    Statistical extremes don't last. Price beyond 2 standard
    deviations has ~95% probability of reverting to mean.

    Uses 15-minute lookback for recent context.
    """

    def __init__(self, weight: float = 1.5, lookback_minutes: int = 15):
        """
        Initialize mean reversion filter.

        Args:
            weight: Filter weight (default: 1.5)
            lookback_minutes: Lookback period for mean calculation (default: 15)
        """
        super().__init__(weight)
        self.lookback_minutes = lookback_minutes
        self.logger.info(
            f"MeanReversionFilter initialized (weight={weight}, "
            f"lookback={lookback_minutes}m)"
        )

    async def evaluate(self, market_data: Any) -> float:
        """
        Evaluate mean reversion opportunity.

        Expected market_data attributes:
        - price_mean_15m: Mean price over last 15 minutes
        - price_std_dev_15m: Standard deviation over last 15 minutes
        - current_price: Current market price

        Returns:
            Score from 0.0 to 1.5
        """
        try:
            # Extract data
            price_mean = getattr(market_data, 'price_mean_15m', None)
            price_std = getattr(market_data, 'price_std_dev_15m', None)
            current_price = getattr(market_data, 'current_price', None)

            if price_mean is None or price_std is None or current_price is None:
                self.log_score(0.0, "- No mean/std data")
                return 0.0

            price_mean = float(price_mean)
            price_std = float(price_std)
            current_price = float(current_price)

            if price_std == 0:
                self.log_score(0.0, "- Zero standard deviation (no price movement)")
                return 0.0

            # Calculate deviation in standard deviations (sigma)
            deviation = abs(current_price - price_mean)
            sigma = deviation / price_std

            # Scoring logic
            if sigma >= 2.0:
                score = self.weight  # Full points for extreme deviation
                self.log_score(
                    score,
                    f"- Extreme deviation: {sigma:.2f}σ (price={current_price:.2f}, "
                    f"mean={price_mean:.2f}, std={price_std:.2f})"
                )
            elif sigma >= 1.0:
                score = self.weight * 0.5  # Half points for moderate deviation
                self.log_score(
                    score,
                    f"- Moderate deviation: {sigma:.2f}σ (price={current_price:.2f}, "
                    f"mean={price_mean:.2f})"
                )
            else:
                score = 0.0  # No points for normal range
                self.log_score(
                    score,
                    f"- Normal range: {sigma:.2f}σ (<1σ threshold)"
                )

            return score

        except Exception as e:
            self.logger.error(f"Error in mean reversion evaluation: {e}")
            return 0.0
