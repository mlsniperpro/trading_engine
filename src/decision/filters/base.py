"""
Base class for secondary signal filters.

Secondary filters provide confluence scoring - they don't block signals,
but add weighted points to increase trade probability assessment.
"""

from abc import ABC, abstractmethod
from typing import Any
import logging

logger = logging.getLogger(__name__)


class SignalFilter(ABC):
    """
    Base class for secondary signal filters.

    Filters provide weighted confluence scoring (0.0 to weight).
    They confirm primary signals but don't block them.

    Design Pattern: Weighted scoring system
    - Each filter has a weight (importance)
    - Returns score from 0.0 to weight
    - Total possible: sum of all weights (10.0 in default config)

    Example weights:
    - Market Profile: 1.5
    - Mean Reversion: 1.5
    - Autocorrelation: 1.0
    - Demand Zone: 2.0
    - Supply Zone: 0.5
    - FVG: 1.5
    """

    def __init__(self, weight: float, name: str = None):
        self.weight = weight
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    @abstractmethod
    async def evaluate(self, market_data: Any) -> float:
        """
        Evaluate market conditions and return score.

        Args:
            market_data: Market data object with analytics results

        Returns:
            Score from 0.0 to self.weight

        Example:
            score = await filter.evaluate(market_data)
            # score will be between 0.0 and filter.weight
        """
        pass

    def log_score(self, score: float, reason: str = "") -> None:
        """Log filter score contribution."""
        percentage = (score / self.weight * 100) if self.weight > 0 else 0
        self.logger.debug(
            f"{self.name}: {score:.2f}/{self.weight:.1f} points ({percentage:.0f}%) {reason}"
        )
