"""
SECONDARY FILTER #4: Demand Zone Filter (Weight: 2.0)

Identifies high-probability support zones where buyers previously stepped in.
Fresh untested zones have highest probability of holding.

Demand zones are created by aggressive buying that exhausts sellers.
Price revisiting these zones often finds support.
"""

from typing import Any, List
import logging

from decision.filters.base import SignalFilter

logger = logging.getLogger(__name__)


class DemandZoneFilter(SignalFilter):
    """
    FILTER #4: Demand zone proximity (weight: 2.0)

    Scoring Logic:
    - Fresh demand zone (untested): +2.0 points (full weight) - highest probability
    - Tested zone (1-2 touches): +1.0 point (50% weight) - still valid
    - Over-tested or no zone: 0 points - zone exhausted

    Key Insight:
    Demand zones mark where strong buyers absorbed selling.
    Fresh zones (never tested) have highest probability of holding.
    Each test weakens the zone as liquidity is consumed.

    Zone Freshness:
    - Fresh: Never tested since creation (is_fresh = True)
    - Valid: Tested 1-2 times (test_count <= 2)
    - Exhausted: Tested 3+ times (avoid)
    """

    def __init__(self, weight: float = 2.0, max_tests_valid: int = 2):
        """
        Initialize demand zone filter.

        Args:
            weight: Filter weight (default: 2.0)
            max_tests_valid: Max test count for valid zone (default: 2)
        """
        super().__init__(weight)
        self.max_tests_valid = max_tests_valid
        self.logger.info(
            f"DemandZoneFilter initialized (weight={weight}, "
            f"max_tests={max_tests_valid})"
        )

    async def evaluate(self, market_data: Any) -> float:
        """
        Evaluate demand zone proximity.

        Expected market_data attributes:
        - demand_zones: List of demand zone objects
          Each zone should have:
          - price_low: Lower boundary
          - price_high: Upper boundary
          - is_fresh: Boolean (never tested)
          - test_count: Number of times tested
        - current_price: Current market price

        Returns:
            Score from 0.0 to 2.0
        """
        try:
            # Extract data
            demand_zones = getattr(market_data, 'demand_zones', None)
            current_price = getattr(market_data, 'current_price', None)

            if demand_zones is None or current_price is None:
                self.log_score(0.0, "- No demand zone data")
                return 0.0

            current_price = float(current_price)

            # Handle empty list or non-list types
            if not isinstance(demand_zones, list) or len(demand_zones) == 0:
                self.log_score(0.0, "- No demand zones available")
                return 0.0

            # Check each zone for price proximity
            best_score = 0.0
            best_zone_info = ""

            for zone in demand_zones:
                try:
                    price_low = float(getattr(zone, 'price_low', 0))
                    price_high = float(getattr(zone, 'price_high', 0))
                    is_fresh = getattr(zone, 'is_fresh', False)
                    test_count = int(getattr(zone, 'test_count', 99))

                    # Check if price is in zone
                    in_zone = price_low <= current_price <= price_high

                    if in_zone:
                        if is_fresh:
                            # Fresh zone - full points
                            score = self.weight
                            zone_info = (
                                f"Fresh zone: {price_low:.2f}-{price_high:.2f}, "
                                f"price={current_price:.2f}"
                            )
                        elif test_count <= self.max_tests_valid:
                            # Tested but still valid - partial points
                            score = self.weight * 0.5
                            zone_info = (
                                f"Tested zone ({test_count}x): {price_low:.2f}-{price_high:.2f}, "
                                f"price={current_price:.2f}"
                            )
                        else:
                            # Over-tested - no points
                            score = 0.0
                            zone_info = (
                                f"Over-tested zone ({test_count}x): {price_low:.2f}-{price_high:.2f}"
                            )

                        # Keep best score
                        if score > best_score:
                            best_score = score
                            best_zone_info = zone_info

                except (AttributeError, ValueError, TypeError) as e:
                    self.logger.debug(f"Skipping invalid zone: {e}")
                    continue

            if best_score > 0:
                self.log_score(best_score, f"- {best_zone_info}")
            else:
                self.log_score(0.0, "- No valid demand zones at current price")

            return best_score

        except Exception as e:
            self.logger.error(f"Error in demand zone evaluation: {e}")
            return 0.0
