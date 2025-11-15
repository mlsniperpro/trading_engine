"""
Multi-Timeframe Manager - Coordinate analysis across multiple timeframes.

Manages:
1. Multi-timeframe candle aggregation (1m, 5m, 15m)
2. Trend alignment checking across timeframes
3. Timeframe coordination for analytics
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """Trend direction."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class TimeframeCandle:
    """Candle for a specific timeframe."""
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: datetime


@dataclass
class MultiTimeframeSnapshot:
    """Snapshot of data across multiple timeframes."""
    symbol: str
    timeframes: List[str]
    candles: Dict[str, TimeframeCandle]
    trends: Dict[str, TrendDirection]
    alignment: str  # 'bullish', 'bearish', 'mixed'
    timestamp: datetime


class MultiTimeframeManager:
    """
    Multi-Timeframe Manager.

    Coordinates analysis across 1m, 5m, and 15m timeframes.

    Timeframe Hierarchy:
    - 15m (Longest): Trend direction, market regime
    - 5m (Middle): Order flow confirmation, trend strength
    - 1m (Fastest): Entry timing, real-time signals

    Alignment Logic:
    - All Bullish = Strong bullish alignment
    - All Bearish = Strong bearish alignment
    - Mixed = No clear alignment (higher risk)
    """

    def __init__(
        self,
        db_manager=None,
        timeframes: List[str] = None
    ):
        """
        Initialize Multi-Timeframe Manager.

        Args:
            db_manager: Database manager for candle queries
            timeframes: List of timeframes to track (default: ['1m', '5m', '15m'])
        """
        self.db_manager = db_manager
        self.timeframes = timeframes or ['1m', '5m', '15m']

        # Cache latest candles per symbol per timeframe
        self._candle_cache: Dict[str, Dict[str, TimeframeCandle]] = {}

        # Cache trend analysis per symbol per timeframe
        self._trend_cache: Dict[str, Dict[str, TrendDirection]] = {}

        logger.info(
            f"MultiTimeframeManager initialized - "
            f"timeframes={self.timeframes}"
        )

    async def get_current_candles(
        self,
        symbol: str,
        timeframes: Optional[List[str]] = None
    ) -> Dict[str, TimeframeCandle]:
        """
        Get current candles for all timeframes.

        Args:
            symbol: Trading pair
            timeframes: Specific timeframes or None for all

        Returns:
            Dict mapping timeframe to candle
        """
        timeframes_to_fetch = timeframes or self.timeframes
        candles = {}

        for tf in timeframes_to_fetch:
            candle = await self._get_latest_candle(symbol, tf)
            if candle:
                candles[tf] = candle

        # Cache for fast access
        cache_key = symbol
        if cache_key not in self._candle_cache:
            self._candle_cache[cache_key] = {}

        self._candle_cache[cache_key].update(candles)

        return candles

    async def check_trend_alignment(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Check trend alignment across all timeframes.

        Returns:
            Dict with alignment status and individual trends
        """
        # Get trends for each timeframe
        trends = {}

        for tf in self.timeframes:
            trend = await self._calculate_trend(symbol, tf)
            trends[tf] = trend

        # Determine overall alignment
        alignment = self._determine_alignment(trends)

        result = {
            'alignment': alignment,
            'trends': {tf: trend.value for tf, trend in trends.items()},
            'timestamp': datetime.utcnow()
        }

        # Cache trends
        self._trend_cache[symbol] = trends

        logger.debug(
            f"Trend alignment for {symbol}: {alignment} "
            f"({', '.join(f'{tf}:{t.value}' for tf, t in trends.items())})"
        )

        return result

    async def _calculate_trend(
        self,
        symbol: str,
        timeframe: str
    ) -> TrendDirection:
        """
        Calculate trend direction for a specific timeframe.

        Simple trend calculation:
        - Compare current close to previous close
        - Use EMA for smoothing (if available)
        - Check candle sequence (higher highs/lows)

        Args:
            symbol: Trading pair
            timeframe: Timeframe to analyze

        Returns:
            TrendDirection
        """
        # Get recent candles
        candles = await self._get_recent_candles(symbol, timeframe, count=5)

        if len(candles) < 2:
            return TrendDirection.NEUTRAL

        # Simple trend: compare current close to oldest close
        current_close = candles[-1]['close']
        previous_close = candles[0]['close']

        price_change_pct = ((current_close - previous_close) / previous_close) * 100

        # Check for higher highs/higher lows (bullish) or lower highs/lower lows (bearish)
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]

        # Bullish: higher highs and higher lows
        if price_change_pct > 0.2 and highs[-1] > highs[0] and lows[-1] > lows[0]:
            return TrendDirection.BULLISH

        # Bearish: lower highs and lower lows
        elif price_change_pct < -0.2 and highs[-1] < highs[0] and lows[-1] < lows[0]:
            return TrendDirection.BEARISH

        # Neutral
        else:
            return TrendDirection.NEUTRAL

    def _determine_alignment(
        self,
        trends: Dict[str, TrendDirection]
    ) -> str:
        """
        Determine overall trend alignment.

        Args:
            trends: Dict of timeframe -> trend

        Returns:
            'bullish', 'bearish', or 'mixed'
        """
        bullish_count = sum(1 for t in trends.values() if t == TrendDirection.BULLISH)
        bearish_count = sum(1 for t in trends.values() if t == TrendDirection.BEARISH)
        total_count = len(trends)

        # All or majority bullish
        if bullish_count == total_count:
            return 'bullish'

        # All or majority bearish
        elif bearish_count == total_count:
            return 'bearish'

        # Mixed trends
        else:
            return 'mixed'

    def get_cached_alignment(self, symbol: str) -> Optional[str]:
        """Get cached trend alignment for a symbol."""
        if symbol not in self._trend_cache:
            return None

        trends = self._trend_cache[symbol]
        return self._determine_alignment(trends)

    async def _get_latest_candle(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[TimeframeCandle]:
        """Get latest candle for a timeframe."""
        # In production, query from DuckDB
        # SELECT * FROM candles_{timeframe} WHERE symbol = ? ORDER BY timestamp DESC LIMIT 1

        # For now, check cache
        cache_key = symbol
        if cache_key in self._candle_cache:
            return self._candle_cache[cache_key].get(timeframe)

        return None

    async def _get_recent_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = 5
    ) -> List[Dict[str, Any]]:
        """Get recent candles for trend calculation."""
        # In production, query from DuckDB
        # SELECT * FROM candles_{timeframe} WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?

        # For now, return empty (placeholder)
        return []

    def add_candle(
        self,
        symbol: str,
        timeframe: str,
        candle: TimeframeCandle
    ):
        """
        Add a candle to cache (for testing).

        Args:
            symbol: Trading pair
            timeframe: Timeframe
            candle: Candle object
        """
        cache_key = symbol
        if cache_key not in self._candle_cache:
            self._candle_cache[cache_key] = {}

        self._candle_cache[cache_key][timeframe] = candle

    def get_snapshot(self, symbol: str) -> Optional[MultiTimeframeSnapshot]:
        """
        Get multi-timeframe snapshot for a symbol.

        Args:
            symbol: Trading pair

        Returns:
            MultiTimeframeSnapshot or None
        """
        if symbol not in self._candle_cache:
            return None

        candles = self._candle_cache.get(symbol, {})
        trends = self._trend_cache.get(symbol, {})

        alignment = self._determine_alignment(trends) if trends else 'unknown'

        return MultiTimeframeSnapshot(
            symbol=symbol,
            timeframes=self.timeframes,
            candles=candles,
            trends=trends,
            alignment=alignment,
            timestamp=datetime.utcnow()
        )


# Example usage and testing
async def test_multi_timeframe():
    """Test multi-timeframe manager."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    manager = MultiTimeframeManager(timeframes=['1m', '5m', '15m'])

    print("="*60)
    print("MULTI-TIMEFRAME COORDINATION TEST")
    print("="*60)

    symbol = 'BTCUSDT'
    now = datetime.utcnow()

    # Add sample candles for different timeframes
    # All bullish candles (uptrend)
    candles_data = {
        '1m': TimeframeCandle(
            symbol=symbol,
            timeframe='1m',
            open=95000,
            high=95100,
            low=94950,
            close=95080,  # Bullish close
            volume=100,
            timestamp=now
        ),
        '5m': TimeframeCandle(
            symbol=symbol,
            timeframe='5m',
            open=94800,
            high=95150,
            low=94750,
            close=95100,  # Bullish close
            volume=500,
            timestamp=now
        ),
        '15m': TimeframeCandle(
            symbol=symbol,
            timeframe='15m',
            open=94500,
            high=95200,
            low=94400,
            close=95150,  # Bullish close
            volume=1500,
            timestamp=now
        )
    }

    # Add candles to manager
    for tf, candle in candles_data.items():
        manager.add_candle(symbol, tf, candle)

    print(f"\nCandles added for {symbol}:")
    for tf, candle in candles_data.items():
        direction = 'BULLISH' if candle.close > candle.open else 'BEARISH'
        print(f"  {tf}: ${candle.close:,.2f} ({direction})")

    # Manually set trends for testing (in production, would be calculated)
    manager._trend_cache[symbol] = {
        '1m': TrendDirection.BULLISH,
        '5m': TrendDirection.BULLISH,
        '15m': TrendDirection.BULLISH
    }

    # Check alignment
    alignment = await manager.check_trend_alignment(symbol)
    print(f"\nTrend Alignment:")
    print(f"  Overall: {alignment['alignment'].upper()}")
    print(f"  Individual trends:")
    for tf, trend in alignment['trends'].items():
        print(f"    {tf}: {trend}")

    # Test with mixed trends
    print("\n" + "-"*60)
    print("Testing MIXED trend scenario:")
    print("-"*60)

    manager._trend_cache[symbol] = {
        '1m': TrendDirection.BEARISH,
        '5m': TrendDirection.NEUTRAL,
        '15m': TrendDirection.BULLISH
    }

    alignment_mixed = await manager.check_trend_alignment(symbol)
    print(f"\nTrend Alignment:")
    print(f"  Overall: {alignment_mixed['alignment'].upper()}")
    print(f"  Individual trends:")
    for tf, trend in alignment_mixed['trends'].items():
        print(f"    {tf}: {trend}")

    # Get snapshot
    snapshot = manager.get_snapshot(symbol)
    if snapshot:
        print(f"\nMulti-Timeframe Snapshot:")
        print(f"  Symbol: {snapshot.symbol}")
        print(f"  Timeframes: {', '.join(snapshot.timeframes)}")
        print(f"  Alignment: {snapshot.alignment}")

    print("\n" + "="*60)


if __name__ == "__main__":
    asyncio.run(test_multi_timeframe())
