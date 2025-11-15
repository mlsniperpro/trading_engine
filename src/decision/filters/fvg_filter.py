"""
SECONDARY FILTER #6: Fair Value Gap (FVG) Filter (Weight: 1.5)

Detects price imbalances that tend to get filled.
FVGs represent inefficient price discovery areas.

Fair Value Gap: 3-candle pattern where middle candle creates a gap.
Price often returns to fill these gaps (mean reversion).
"""

from typing import Any, List
import logging

from decision.filters.base import SignalFilter

logger = logging.getLogger(__name__)


class FairValueGapFilter(SignalFilter):
    """
    FILTER #6: Fair value gap detection (weight: 1.5)

    Scoring Logic:
    - Unfilled FVG at current price: +1.5 points (full weight)
    - Partially filled FVG: +0.75 points (50% weight)
    - No FVG or filled: 0 points

    Key Insight:
    FVGs mark price inefficiencies where market moved too fast.
    These gaps tend to get filled as price revisits for "fair value".

    FVG Pattern (Bullish):
    - Candle 1 high < Candle 3 low = Gap created
    - Gap = imbalance, likely to be filled

    FVG Pattern (Bearish):
    - Candle 1 low > Candle 3 high = Gap created

    Zone Status:
    - Unfilled: Price hasn't touched gap yet (is_filled = False)
    - Partially filled: Price entered but didn't close gap
    - Filled: Price completely filled gap
    """

    def __init__(self, weight: float = 1.5):
        """
        Initialize fair value gap filter.

        Args:
            weight: Filter weight (default: 1.5)
        """
        super().__init__(weight)
        self.logger.info(f"FairValueGapFilter initialized (weight={weight})")

    async def evaluate(self, market_data: Any) -> float:
        """
        Evaluate fair value gap proximity.

        Expected market_data attributes:
        - fair_value_gaps: List of FVG objects
          Each FVG should have:
          - gap_low: Lower boundary of gap
          - gap_high: Upper boundary of gap
          - is_filled: Boolean (gap completely filled)
          - direction: 'bullish' or 'bearish'
        - current_price: Current market price

        Returns:
            Score from 0.0 to 1.5
        """
        try:
            # Extract data
            fvgs = getattr(market_data, 'fair_value_gaps', None)
            current_price = getattr(market_data, 'current_price', None)

            if fvgs is None or current_price is None:
                self.log_score(0.0, "- No FVG data")
                return 0.0

            current_price = float(current_price)

            # Handle empty list or non-list types
            if not isinstance(fvgs, list) or len(fvgs) == 0:
                self.log_score(0.0, "- No FVGs available")
                return 0.0

            # Find best FVG at current price
            best_score = 0.0
            best_fvg_info = ""

            for fvg in fvgs:
                try:
                    gap_low = float(getattr(fvg, 'gap_low', 0))
                    gap_high = float(getattr(fvg, 'gap_high', 0))
                    is_filled = getattr(fvg, 'is_filled', True)
                    direction = getattr(fvg, 'direction', 'unknown')

                    # Check if price is in gap
                    in_gap = gap_low <= current_price <= gap_high

                    if in_gap:
                        if not is_filled:
                            # Unfilled gap - full points
                            score = self.weight
                            fvg_info = (
                                f"Unfilled {direction} FVG: {gap_low:.2f}-{gap_high:.2f}, "
                                f"price={current_price:.2f}"
                            )
                        else:
                            # Partially filled gap - half points
                            # (if price is in gap but gap is marked filled, it's being filled now)
                            score = self.weight * 0.5
                            fvg_info = (
                                f"Filling {direction} FVG: {gap_low:.2f}-{gap_high:.2f}, "
                                f"price={current_price:.2f}"
                            )

                        # Keep best score
                        if score > best_score:
                            best_score = score
                            best_fvg_info = fvg_info

                    # Alternative: Check if price is NEAR unfilled gap (within gap zone)
                    # This catches FVGs that price is approaching
                    elif not is_filled:
                        # Check if price is approaching gap from correct direction
                        gap_center = (gap_low + gap_high) / 2
                        gap_size = gap_high - gap_low
                        distance = abs(current_price - gap_center)

                        # If price is within 1 gap-size of the gap, give partial credit
                        if distance < gap_size:
                            score = self.weight * 0.3
                            approach = "above" if current_price > gap_high else "below"
                            fvg_info = (
                                f"Approaching unfilled {direction} FVG from {approach}: "
                                f"{gap_low:.2f}-{gap_high:.2f}, price={current_price:.2f}"
                            )

                            if score > best_score:
                                best_score = score
                                best_fvg_info = fvg_info

                except (AttributeError, ValueError, TypeError) as e:
                    self.logger.debug(f"Skipping invalid FVG: {e}")
                    continue

            if best_score > 0:
                self.log_score(best_score, f"- {best_fvg_info}")
            else:
                self.log_score(0.0, "- No relevant FVGs at current price")

            return best_score

        except Exception as e:
            self.logger.error(f"Error in FVG evaluation: {e}")
            return 0.0
