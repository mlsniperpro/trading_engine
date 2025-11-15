"""
SECONDARY FILTER #5: Supply Zone Filter (Weight: 0.5)

Identifies resistance zones as profit targets.
Lower weight since this confirms exit targets, not entry quality.

Supply zones mark where sellers previously overwhelmed buyers.
Used primarily for target selection on long entries.
"""

from typing import Any, List
import logging

from decision.filters.base import SignalFilter

logger = logging.getLogger(__name__)


class SupplyZoneFilter(SignalFilter):
    """
    FILTER #5: Supply zone as target (weight: 0.5)

    Scoring Logic:
    - Supply zone above current price: +0.5 points - valid profit target
    - No supply zone above: 0 points - no clear target

    Key Insight:
    Supply zones provide logical profit targets for long entries.
    This filter has lower weight (0.5) because it confirms exit targets,
    not entry quality. Entry quality comes from demand zones and other factors.

    For long entries: We want supply zone ABOVE price (target)
    For short entries: We want demand zone BELOW price (target)
    """

    def __init__(self, weight: float = 0.5, min_distance_pct: float = 0.005):
        """
        Initialize supply zone filter.

        Args:
            weight: Filter weight (default: 0.5)
            min_distance_pct: Min distance from price for valid target (default: 0.5%)
        """
        super().__init__(weight)
        self.min_distance_pct = min_distance_pct
        self.logger.info(
            f"SupplyZoneFilter initialized (weight={weight}, "
            f"min_distance={min_distance_pct*100}%)"
        )

    async def evaluate(self, market_data: Any) -> float:
        """
        Evaluate supply zone as profit target.

        Expected market_data attributes:
        - supply_zones: List of supply zone objects
          Each zone should have:
          - price_low: Lower boundary
          - price_high: Upper boundary
        - current_price: Current market price

        Returns:
            Score from 0.0 to 0.5
        """
        try:
            # Extract data
            supply_zones = getattr(market_data, 'supply_zones', None)
            current_price = getattr(market_data, 'current_price', None)

            if supply_zones is None or current_price is None:
                self.log_score(0.0, "- No supply zone data")
                return 0.0

            current_price = float(current_price)

            # Handle empty list or non-list types
            if not isinstance(supply_zones, list) or len(supply_zones) == 0:
                self.log_score(0.0, "- No supply zones available")
                return 0.0

            # Find nearest supply zone above current price
            min_distance = current_price * self.min_distance_pct
            nearest_zone = None
            nearest_distance = float('inf')

            for zone in supply_zones:
                try:
                    price_low = float(getattr(zone, 'price_low', 0))
                    price_high = float(getattr(zone, 'price_high', 0))

                    # Check if zone is above current price
                    if price_low > current_price:
                        # Use zone low as target (first resistance)
                        distance = price_low - current_price

                        # Must be far enough away to be meaningful
                        if distance >= min_distance and distance < nearest_distance:
                            nearest_distance = distance
                            nearest_zone = {
                                'price_low': price_low,
                                'price_high': price_high,
                                'distance': distance
                            }

                except (AttributeError, ValueError, TypeError) as e:
                    self.logger.debug(f"Skipping invalid zone: {e}")
                    continue

            # Scoring
            if nearest_zone:
                score = self.weight
                distance_pct = (nearest_zone['distance'] / current_price) * 100
                self.log_score(
                    score,
                    f"- Target zone found: {nearest_zone['price_low']:.2f}-{nearest_zone['price_high']:.2f} "
                    f"(+{distance_pct:.1f}% from price={current_price:.2f})"
                )
            else:
                score = 0.0
                self.log_score(0.0, "- No supply zone above current price")

            return score

        except Exception as e:
            self.logger.error(f"Error in supply zone evaluation: {e}")
            return 0.0
