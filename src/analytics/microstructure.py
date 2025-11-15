"""
Microstructure Analyzer - Price rejection and candle strength analysis.

Detects:
1. Price rejection patterns (pin bars, wicks)
2. Candle strength (body vs wick ratio)
3. Bullish/Bearish rejection patterns
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Candle:
    """Represents a candlestick."""
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: datetime
    timeframe: str = '1m'


@dataclass
class RejectionPattern:
    """Rejection pattern detection result."""
    detected: bool
    type: str  # 'bullish', 'bearish', 'none'
    strength: float  # 0-1 score
    pattern_name: str  # 'pin_bar', 'hammer', 'shooting_star', etc.
    upper_wick_ratio: float
    lower_wick_ratio: float
    body_ratio: float
    description: str


class MicrostructureAnalyzer:
    """
    Microstructure Analyzer - Price action and candle pattern detection.

    Detects rejection patterns:
    1. Pin Bars - Long wicks showing rejection
    2. Hammers - Bullish rejection at support
    3. Shooting Stars - Bearish rejection at resistance
    4. Doji - Indecision candles

    Candle Strength Analysis:
    - Strong candle: Large body, small wicks
    - Weak candle: Small body, large wicks
    - Rejection candle: One long wick, small body
    """

    def __init__(
        self,
        min_wick_ratio: float = 0.5,  # Min wick/range ratio for rejection
        min_body_ratio: float = 0.1,  # Min body size for valid pattern
        min_rejection_strength: float = 0.6  # Min strength score to signal
    ):
        """
        Initialize Microstructure Analyzer.

        Args:
            min_wick_ratio: Minimum wick to range ratio for rejection (0.5 = 50%)
            min_body_ratio: Minimum body size for valid candle pattern
            min_rejection_strength: Minimum strength score to detect rejection
        """
        self.min_wick_ratio = min_wick_ratio
        self.min_body_ratio = min_body_ratio
        self.min_rejection_strength = min_rejection_strength

        logger.info(
            f"MicrostructureAnalyzer initialized - "
            f"min_wick_ratio={min_wick_ratio}, min_rejection_strength={min_rejection_strength}"
        )

    async def detect_rejection(
        self,
        symbol: str,
        candle: Optional[Candle] = None
    ) -> Dict[str, Any]:
        """
        Detect price rejection patterns.

        Args:
            symbol: Trading pair
            candle: Candle to analyze (if None, fetches latest)

        Returns:
            Dict with detected, type, strength, pattern details
        """
        # In production, fetch latest candle from DB if not provided
        if candle is None:
            # Placeholder - would query DuckDB
            return {
                'detected': False,
                'type': 'none',
                'strength': 0,
                'pattern_name': 'none',
                'description': 'No candle data available'
            }

        # Calculate candle metrics
        candle_range = candle.high - candle.low
        body_size = abs(candle.close - candle.open)

        if candle_range == 0:
            return {
                'detected': False,
                'type': 'none',
                'strength': 0,
                'pattern_name': 'invalid',
                'description': 'Zero range candle'
            }

        # Calculate wick sizes
        if candle.close > candle.open:  # Bullish candle
            upper_wick = candle.high - candle.close
            lower_wick = candle.open - candle.low
            is_bullish_body = True
        else:  # Bearish candle
            upper_wick = candle.high - candle.open
            lower_wick = candle.close - candle.low
            is_bullish_body = False

        # Calculate ratios
        upper_wick_ratio = upper_wick / candle_range
        lower_wick_ratio = lower_wick / candle_range
        body_ratio = body_size / candle_range

        # Detect patterns
        pattern = self._detect_pattern(
            upper_wick_ratio,
            lower_wick_ratio,
            body_ratio,
            is_bullish_body,
            candle
        )

        logger.debug(
            f"Rejection analysis for {symbol}: {pattern.pattern_name} "
            f"(strength: {pattern.strength:.2f})"
        )

        return {
            'detected': pattern.detected,
            'type': pattern.type,
            'strength': pattern.strength,
            'pattern_name': pattern.pattern_name,
            'upper_wick_ratio': upper_wick_ratio,
            'lower_wick_ratio': lower_wick_ratio,
            'body_ratio': body_ratio,
            'description': pattern.description
        }

    def _detect_pattern(
        self,
        upper_wick_ratio: float,
        lower_wick_ratio: float,
        body_ratio: float,
        is_bullish_body: bool,
        candle: Candle
    ) -> RejectionPattern:
        """
        Detect specific candle pattern.

        Patterns:
        1. Bullish Pin Bar / Hammer - Long lower wick, small upper wick, small body
        2. Bearish Pin Bar / Shooting Star - Long upper wick, small lower wick, small body
        3. Doji - Very small body, wicks can vary

        Args:
            upper_wick_ratio: Upper wick / range
            lower_wick_ratio: Lower wick / range
            body_ratio: Body size / range
            is_bullish_body: True if close > open
            candle: Candle object

        Returns:
            RejectionPattern object
        """
        # Bullish Rejection (Hammer / Bullish Pin Bar)
        if (lower_wick_ratio >= self.min_wick_ratio and
            upper_wick_ratio < 0.2 and
            body_ratio >= self.min_body_ratio):

            strength = lower_wick_ratio
            pattern_name = 'hammer' if is_bullish_body else 'bullish_pin_bar'

            return RejectionPattern(
                detected=strength >= self.min_rejection_strength,
                type='bullish',
                strength=strength,
                pattern_name=pattern_name,
                upper_wick_ratio=upper_wick_ratio,
                lower_wick_ratio=lower_wick_ratio,
                body_ratio=body_ratio,
                description=f"Bullish rejection at ${candle.low:.2f} - buyers defended support"
            )

        # Bearish Rejection (Shooting Star / Bearish Pin Bar)
        elif (upper_wick_ratio >= self.min_wick_ratio and
              lower_wick_ratio < 0.2 and
              body_ratio >= self.min_body_ratio):

            strength = upper_wick_ratio
            pattern_name = 'shooting_star' if not is_bullish_body else 'bearish_pin_bar'

            return RejectionPattern(
                detected=strength >= self.min_rejection_strength,
                type='bearish',
                strength=strength,
                pattern_name=pattern_name,
                upper_wick_ratio=upper_wick_ratio,
                lower_wick_ratio=lower_wick_ratio,
                body_ratio=body_ratio,
                description=f"Bearish rejection at ${candle.high:.2f} - sellers defended resistance"
            )

        # Doji (Indecision)
        elif body_ratio < 0.1:
            strength = 1 - body_ratio  # Smaller body = stronger doji

            return RejectionPattern(
                detected=False,  # Doji alone is not a rejection
                type='neutral',
                strength=strength,
                pattern_name='doji',
                upper_wick_ratio=upper_wick_ratio,
                lower_wick_ratio=lower_wick_ratio,
                body_ratio=body_ratio,
                description="Doji candle - market indecision"
            )

        # No pattern
        else:
            return RejectionPattern(
                detected=False,
                type='none',
                strength=0,
                pattern_name='none',
                upper_wick_ratio=upper_wick_ratio,
                lower_wick_ratio=lower_wick_ratio,
                body_ratio=body_ratio,
                description="No rejection pattern detected"
            )

    def analyze_candle_strength(self, candle: Candle) -> Dict[str, Any]:
        """
        Analyze candle strength (body vs wick ratio).

        Strong candle = Large body, small wicks
        Weak candle = Small body, large wicks

        Args:
            candle: Candle to analyze

        Returns:
            Dict with strength score, type, description
        """
        candle_range = candle.high - candle.low
        body_size = abs(candle.close - candle.open)

        if candle_range == 0:
            return {
                'strength': 0,
                'type': 'invalid',
                'description': 'Zero range candle'
            }

        body_ratio = body_size / candle_range

        # Determine strength
        if body_ratio >= 0.7:
            strength_type = 'very_strong'
            description = "Very strong candle - decisive move"
        elif body_ratio >= 0.5:
            strength_type = 'strong'
            description = "Strong candle - clear direction"
        elif body_ratio >= 0.3:
            strength_type = 'moderate'
            description = "Moderate candle - some conviction"
        elif body_ratio >= 0.15:
            strength_type = 'weak'
            description = "Weak candle - lack of conviction"
        else:
            strength_type = 'very_weak'
            description = "Very weak candle - indecision or rejection"

        # Direction
        direction = 'bullish' if candle.close > candle.open else 'bearish'

        return {
            'strength': body_ratio,
            'type': strength_type,
            'direction': direction,
            'description': description,
            'close_position': self._analyze_close_position(candle)
        }

    def _analyze_close_position(self, candle: Candle) -> Dict[str, Any]:
        """
        Analyze where the close is relative to the range.

        Close at top of range = Bullish
        Close at bottom of range = Bearish
        Close in middle = Neutral

        Args:
            candle: Candle to analyze

        Returns:
            Dict with position ratio and interpretation
        """
        candle_range = candle.high - candle.low

        if candle_range == 0:
            return {'ratio': 0.5, 'position': 'middle'}

        # Close position as ratio (0 = low, 1 = high)
        close_ratio = (candle.close - candle.low) / candle_range

        if close_ratio >= 0.8:
            position = 'top'
            interpretation = 'Strong bullish close'
        elif close_ratio >= 0.6:
            position = 'upper'
            interpretation = 'Bullish close'
        elif close_ratio >= 0.4:
            position = 'middle'
            interpretation = 'Neutral close'
        elif close_ratio >= 0.2:
            position = 'lower'
            interpretation = 'Bearish close'
        else:
            position = 'bottom'
            interpretation = 'Strong bearish close'

        return {
            'ratio': close_ratio,
            'position': position,
            'interpretation': interpretation
        }


# Example usage and testing
async def test_microstructure():
    """Test microstructure analyzer with sample candles."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    analyzer = MicrostructureAnalyzer(
        min_wick_ratio=0.5,
        min_rejection_strength=0.6
    )

    print("="*60)
    print("MICROSTRUCTURE ANALYSIS TEST")
    print("="*60)

    # Test 1: Bullish Hammer (rejection at support)
    print("\n1. Bullish Hammer:")
    hammer = Candle(
        symbol='BTCUSDT',
        open=95000,
        high=95200,
        low=94500,  # Long lower wick
        close=95100,
        volume=100,
        timestamp=datetime.utcnow()
    )
    result = await analyzer.detect_rejection('BTCUSDT', hammer)
    print(f"   Pattern: {result['pattern_name']}")
    print(f"   Type: {result['type']}")
    print(f"   Strength: {result['strength']:.2f}")
    print(f"   Description: {result['description']}")

    # Test 2: Bearish Shooting Star (rejection at resistance)
    print("\n2. Bearish Shooting Star:")
    shooting_star = Candle(
        symbol='BTCUSDT',
        open=95000,
        high=95500,  # Long upper wick
        low=94900,
        close=94950,
        volume=100,
        timestamp=datetime.utcnow()
    )
    result = await analyzer.detect_rejection('BTCUSDT', shooting_star)
    print(f"   Pattern: {result['pattern_name']}")
    print(f"   Type: {result['type']}")
    print(f"   Strength: {result['strength']:.2f}")
    print(f"   Description: {result['description']}")

    # Test 3: Doji (indecision)
    print("\n3. Doji:")
    doji = Candle(
        symbol='BTCUSDT',
        open=95000,
        high=95100,
        low=94900,
        close=95005,  # Almost same as open
        volume=100,
        timestamp=datetime.utcnow()
    )
    result = await analyzer.detect_rejection('BTCUSDT', doji)
    print(f"   Pattern: {result['pattern_name']}")
    print(f"   Body Ratio: {result['body_ratio']:.3f}")
    print(f"   Description: {result['description']}")

    # Test 4: Strong Bullish Candle
    print("\n4. Strong Bullish Candle:")
    strong_bull = Candle(
        symbol='BTCUSDT',
        open=95000,
        high=95800,
        low=94900,
        close=95750,  # Close near high
        volume=200,
        timestamp=datetime.utcnow()
    )
    strength = analyzer.analyze_candle_strength(strong_bull)
    print(f"   Strength: {strength['type']} ({strength['strength']:.2f})")
    print(f"   Direction: {strength['direction']}")
    print(f"   Close Position: {strength['close_position']['interpretation']}")

    print("\n" + "="*60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_microstructure())
