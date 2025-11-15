"""
PRIMARY SIGNAL #2: Microstructure Analyzer

Detects price rejection patterns at key levels.
Identifies absorption vs breakout behavior through candle analysis.

Rejection patterns indicate strong support/resistance where price
was aggressively rejected, suggesting future reversals.
"""

from typing import Any
import logging

from decision.analyzers.base import SignalAnalyzer
from decision.signal_pipeline import SignalResult

logger = logging.getLogger(__name__)


class MicrostructureAnalyzer(SignalAnalyzer):
    """
    PRIMARY SIGNAL #2: Price rejection pattern detection.

    Analyzes candlestick microstructure to detect:
    - Bullish rejections (pin bars with long lower wicks)
    - Bearish rejections (pin bars with long upper wicks)
    - Absorption behavior (buying/selling into support/resistance)

    Key Pattern: Pin Bar / Hammer / Shooting Star
    - Long wick (>2x body size) shows rejection
    - Close near opposite end shows strength
    - Body position indicates direction

    Bullish Rejection:
    - Long lower wick (>2x body)
    - Close > open (green candle)
    - Close in upper 80% of range

    Bearish Rejection:
    - Long upper wick (>2x body)
    - Close < open (red candle)
    - Close in lower 20% of range
    """

    def __init__(self, min_wick_ratio: float = 2.0, min_close_ratio: float = 0.8):
        """
        Initialize microstructure analyzer.

        Args:
            min_wick_ratio: Min ratio of wick to body for rejection (default: 2.0)
            min_close_ratio: Min close position in range for strong rejection (default: 0.8)
        """
        super().__init__()
        self.min_wick_ratio = min_wick_ratio
        self.min_close_ratio = min_close_ratio
        self.logger.info(
            f"MicrostructureAnalyzer initialized (wick_ratio={min_wick_ratio}, "
            f"close_ratio={min_close_ratio})"
        )

    async def analyze(self, market_data: Any) -> SignalResult:
        """
        Analyze price microstructure for rejection patterns.

        Expected market_data attributes:
        - latest_candle_1m: Candle object with OHLC data
          - open, high, low, close

        Returns:
            SignalResult with pass/fail and direction
        """
        try:
            # Extract candle data
            candle = getattr(market_data, 'latest_candle_1m', None)

            if candle is None:
                return SignalResult(
                    passed=False,
                    strength=0.0,
                    reason="No candle data available",
                    direction=None,
                    metadata={}
                )

            # Extract OHLC
            open_price = float(getattr(candle, 'open', 0))
            high = float(getattr(candle, 'high', 0))
            low = float(getattr(candle, 'low', 0))
            close = float(getattr(candle, 'close', 0))

            # Validate data
            if high == 0 or low == 0 or high <= low:
                return SignalResult(
                    passed=False,
                    strength=0.0,
                    reason="Invalid candle data",
                    direction=None,
                    metadata={'open': open_price, 'high': high, 'low': low, 'close': close}
                )

            # Calculate candle components
            body_size = abs(close - open_price)
            upper_wick = high - max(close, open_price)
            lower_wick = min(close, open_price) - low
            total_range = high - low

            # Avoid division by zero
            if total_range == 0:
                return SignalResult(
                    passed=False,
                    strength=0.0,
                    reason="Zero range candle (no price movement)",
                    direction=None,
                    metadata={'body_size': 0, 'range': 0}
                )

            # Calculate close position in range (0 = low, 1 = high)
            close_position = (close - low) / total_range if total_range > 0 else 0.5

            # Detect bullish rejection
            bullish_rejection = (
                lower_wick > body_size * self.min_wick_ratio and
                close > open_price and  # Green candle
                close_position > self.min_close_ratio  # Close in upper portion
            )

            # Detect bearish rejection
            bearish_rejection = (
                upper_wick > body_size * self.min_wick_ratio and
                close < open_price and  # Red candle
                close_position < (1 - self.min_close_ratio)  # Close in lower portion
            )

            # Determine signal
            if bullish_rejection:
                passed = True
                direction = 'long'
                strength = min(lower_wick / body_size / 5.0, 1.0) if body_size > 0 else 0.8
                reason = (
                    f"Bullish rejection: lower wick={lower_wick:.2f} "
                    f"({lower_wick/body_size:.1f}x body), close @{close_position*100:.0f}% of range"
                )
            elif bearish_rejection:
                passed = True
                direction = 'short'
                strength = min(upper_wick / body_size / 5.0, 1.0) if body_size > 0 else 0.8
                reason = (
                    f"Bearish rejection: upper wick={upper_wick:.2f} "
                    f"({upper_wick/body_size:.1f}x body), close @{close_position*100:.0f}% of range"
                )
            else:
                passed = False
                direction = None
                strength = 0.0
                max_wick = max(upper_wick, lower_wick)
                wick_ratio = max_wick / body_size if body_size > 0 else 0
                reason = (
                    f"No rejection pattern: max wick={max_wick:.2f} "
                    f"({wick_ratio:.1f}x body, need >{self.min_wick_ratio}x)"
                )

            result = SignalResult(
                passed=passed,
                strength=strength,
                reason=reason,
                direction=direction,
                metadata={
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'close': close,
                    'body_size': body_size,
                    'upper_wick': upper_wick,
                    'lower_wick': lower_wick,
                    'total_range': total_range,
                    'close_position': close_position,
                    'bullish_rejection': bullish_rejection,
                    'bearish_rejection': bearish_rejection
                }
            )

            self.log_result(result)
            return result

        except Exception as e:
            self.logger.error(f"Error in microstructure analysis: {e}")
            return SignalResult(
                passed=False,
                strength=0.0,
                reason=f"Analysis error: {str(e)}",
                direction=None,
                metadata={}
            )
