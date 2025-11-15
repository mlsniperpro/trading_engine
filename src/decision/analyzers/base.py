"""
Base class for primary signal analyzers.

Primary analyzers detect entry triggers and MUST all pass for signal generation.
Examples:
- Order flow imbalance
- Microstructure rejection patterns
"""

from abc import ABC, abstractmethod
from typing import Any
import logging

from decision.signal_pipeline import SignalResult

logger = logging.getLogger(__name__)


class SignalAnalyzer(ABC):
    """
    Base class for primary signal analyzers.

    Primary analyzers are entry triggers - ALL must pass for signal generation.
    They return a SignalResult with pass/fail, strength, and reasoning.

    Design Pattern: Composition over inheritance
    - Each analyzer is independent and testable
    - DecisionEngine composes multiple analyzers
    - Easy to add/remove analyzers without modifying core logic
    """

    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    @abstractmethod
    async def analyze(self, market_data: Any) -> SignalResult:
        """
        Analyze market data and return signal result.

        Args:
            market_data: Market data object with tick data, candles, etc.

        Returns:
            SignalResult with pass/fail, strength, and reasoning

        Example:
            result = await analyzer.analyze(market_data)
            if result.passed:
                print(f"Signal passed: {result.reason}")
        """
        pass

    def log_result(self, result: SignalResult) -> None:
        """Log analysis result."""
        if result.passed:
            self.logger.info(f"✅ {self.name}: {result.reason} (strength={result.strength:.2f})")
        else:
            self.logger.debug(f"❌ {self.name}: {result.reason}")
