"""
SECONDARY FILTER #1: Market Profile Filter (Weight: 1.5)

Analyzes value area positioning to increase signal probability.
Trading at VAH/VAL extremes provides high-probability reversal zones.

Value Area: 70% of volume distribution (middle prices)
VAH: Value Area High (upper boundary)
VAL: Value Area Low (lower boundary)
POC: Point of Control (highest volume price)
"""

from typing import Any
import logging

from decision.filters.base import SignalFilter

logger = logging.getLogger(__name__)


class MarketProfileFilter(SignalFilter):
    """
    FILTER #1: Market profile analysis (weight: 1.5)

    Scoring Logic:
    - At VAH or VAL: +1.5 points (full weight) - extremes are reversal zones
    - Inside value area: +0.5 points (33% weight) - moderate confluence
    - Outside value area: 0 points - wrong side of value

    Key Insight:
    Price tends to revert to value area. Trading at extremes
    (VAH/VAL) provides best risk/reward for mean reversion.
    """

    def __init__(self, weight: float = 1.5, extreme_threshold_pct: float = 0.001):
        """
        Initialize market profile filter.

        Args:
            weight: Filter weight (default: 1.5)
            extreme_threshold_pct: % threshold for "at VAH/VAL" (default: 0.1%)
        """
        super().__init__(weight)
        self.extreme_threshold_pct = extreme_threshold_pct
        self.logger.info(
            f"MarketProfileFilter initialized (weight={weight}, "
            f"extreme_threshold={extreme_threshold_pct*100}%)"
        )

    async def evaluate(self, market_data: Any) -> float:
        """
        Evaluate market profile positioning.

        Expected market_data attributes:
        - market_profile_15m: Profile object with VAH, VAL, POC
          - value_area_high (VAH)
          - value_area_low (VAL)
          - point_of_control (POC)
        - current_price: Current market price

        Returns:
            Score from 0.0 to 1.5
        """
        try:
            # Extract data
            profile = getattr(market_data, 'market_profile_15m', None)
            current_price = getattr(market_data, 'current_price', None)

            if profile is None or current_price is None:
                self.log_score(0.0, "- No profile data")
                return 0.0

            vah = float(getattr(profile, 'value_area_high', 0))
            val = float(getattr(profile, 'value_area_low', 0))
            poc = float(getattr(profile, 'point_of_control', 0))

            if vah == 0 or val == 0:
                self.log_score(0.0, "- Invalid profile data")
                return 0.0

            current_price = float(current_price)

            # Calculate thresholds for "at VAH/VAL"
            vah_threshold = vah * self.extreme_threshold_pct
            val_threshold = val * self.extreme_threshold_pct

            # Check position
            at_vah = abs(current_price - vah) < vah_threshold
            at_val = abs(current_price - val) < val_threshold
            inside_value = val < current_price < vah

            # Scoring logic
            if at_vah or at_val:
                score = self.weight  # Full points at extremes
                location = "VAH" if at_vah else "VAL"
                self.log_score(
                    score,
                    f"- At {location}: price={current_price:.2f}, {location}={vah if at_vah else val:.2f}"
                )
            elif inside_value:
                score = self.weight * 0.33  # Partial points inside value area
                self.log_score(
                    score,
                    f"- Inside value area: price={current_price:.2f}, VAL={val:.2f}, VAH={vah:.2f}"
                )
            else:
                score = 0.0  # No points outside value area
                position = "above VAH" if current_price > vah else "below VAL"
                self.log_score(
                    score,
                    f"- Outside value area ({position}): price={current_price:.2f}"
                )

            return score

        except Exception as e:
            self.logger.error(f"Error in market profile evaluation: {e}")
            return 0.0
