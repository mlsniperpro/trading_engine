"""
Confluence Score Calculator

Aggregates primary analyzer results and secondary filter scores
to produce a final confluence score for trade signal generation.

MAX POSSIBLE SCORE: 10.0 points
- Market Profile: 1.5
- Mean Reversion: 1.5
- Autocorrelation: 1.0
- Demand Zone: 2.0
- Supply Zone: 0.5
- Fair Value Gap: 1.5
- Liquidity: 2.0 (optional, not implemented yet)
"""

from dataclasses import dataclass
from typing import List, Dict, Any
import logging

from decision.signal_pipeline import SignalResult

logger = logging.getLogger(__name__)


@dataclass
class ConfluenceResult:
    """
    Result from confluence calculation.

    Attributes:
        score: Total confluence score (0.0 to max_possible)
        max_possible: Maximum possible score from configured filters
        primary_passed: Whether all primary analyzers passed
        primary_direction: Direction from primary analyzers ('long', 'short', or None)
        filter_contributions: Dict of filter name -> score contribution
        primary_results: List of primary analyzer results
    """
    score: float
    max_possible: float
    primary_passed: bool
    primary_direction: str  # 'long', 'short', or None
    filter_contributions: Dict[str, float]
    primary_results: List[SignalResult]

    @property
    def percentage(self) -> float:
        """Confluence score as percentage of maximum possible."""
        if self.max_possible == 0:
            return 0.0
        return (self.score / self.max_possible) * 100

    def __repr__(self) -> str:
        return (
            f"ConfluenceResult(score={self.score:.1f}/{self.max_possible:.1f}, "
            f"{self.percentage:.0f}%, direction={self.primary_direction})"
        )


class ConfluenceCalculator:
    """
    Calculates weighted confluence score from primary signals and secondary filters.

    Design:
    1. Check ALL primary analyzers (must all pass)
    2. Verify directional agreement (all must agree on long/short)
    3. Sum secondary filter scores (weighted contribution)
    4. Return confluence result with score and metadata

    This is a pure calculation component - no side effects or state.
    """

    def __init__(self, name: str = "ConfluenceCalculator"):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    async def calculate(
        self,
        primary_results: List[SignalResult],
        filter_scores: Dict[str, float],
        max_possible_score: float = 10.0
    ) -> ConfluenceResult:
        """
        Calculate confluence score from analyzer results and filter scores.

        Args:
            primary_results: Results from all primary analyzers
            filter_scores: Dict of filter_name -> score
            max_possible_score: Maximum possible confluence score

        Returns:
            ConfluenceResult with score and analysis

        Logic:
        1. Check if ALL primary analyzers passed
        2. Check if all primary analyzers agree on direction
        3. Calculate total secondary filter score
        4. Return confluence result
        """

        # Step 1: Check if all primary analyzers passed
        all_passed = all(result.passed for result in primary_results)

        if not all_passed:
            failed = [r for r in primary_results if not r.passed]
            self.logger.debug(
                f"Primary analyzers failed: {[r.reason for r in failed]}"
            )
            return ConfluenceResult(
                score=0.0,
                max_possible=max_possible_score,
                primary_passed=False,
                primary_direction=None,
                filter_contributions={},
                primary_results=primary_results
            )

        # Step 2: Check directional agreement
        directions = [r.direction for r in primary_results if r.direction]

        if not directions:
            self.logger.warning("Primary analyzers passed but no direction specified")
            return ConfluenceResult(
                score=0.0,
                max_possible=max_possible_score,
                primary_passed=True,
                primary_direction=None,
                filter_contributions={},
                primary_results=primary_results
            )

        # Check if all directions agree
        first_direction = directions[0]
        if not all(d == first_direction for d in directions):
            self.logger.warning(
                f"Primary analyzers conflict on direction: {directions}"
            )
            return ConfluenceResult(
                score=0.0,
                max_possible=max_possible_score,
                primary_passed=True,
                primary_direction=None,
                filter_contributions={},
                primary_results=primary_results
            )

        # Step 3: Calculate total confluence score from secondary filters
        total_score = sum(filter_scores.values())

        self.logger.info(
            f"✅ Confluence calculated: {total_score:.1f}/{max_possible_score:.1f} "
            f"({total_score/max_possible_score*100:.0f}%) - Direction: {first_direction.upper()}"
        )

        # Log individual contributions
        for filter_name, score in sorted(filter_scores.items(), key=lambda x: x[1], reverse=True):
            if score > 0:
                self.logger.debug(f"  • {filter_name}: +{score:.2f} points")

        return ConfluenceResult(
            score=total_score,
            max_possible=max_possible_score,
            primary_passed=True,
            primary_direction=first_direction,
            filter_contributions=filter_scores,
            primary_results=primary_results
        )

    def get_confidence_level(self, score: float, max_score: float = 10.0) -> str:
        """
        Get confidence level based on confluence score.

        Score ranges:
        - >= 7.0: very_high (70%+)
        - >= 5.0: high (50-70%)
        - >= 4.0: medium (40-50%)
        - >= 3.0: low (30-40%)
        - < 3.0: insufficient (below threshold)

        Args:
            score: Confluence score
            max_score: Maximum possible score

        Returns:
            Confidence level string
        """
        percentage = (score / max_score) * 100 if max_score > 0 else 0

        if score >= 7.0:
            return 'very_high'
        elif score >= 5.0:
            return 'high'
        elif score >= 4.0:
            return 'medium'
        elif score >= 3.0:
            return 'low'
        else:
            return 'insufficient'
