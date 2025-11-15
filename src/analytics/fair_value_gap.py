"""
Fair Value Gap (FVG) Detector - Identify and track price inefficiencies.

Fair Value Gaps (FVG):
- Bullish FVG: Gap between candle 1 high and candle 3 low (unfilled demand)
- Bearish FVG: Gap between candle 1 low and candle 3 high (unfilled supply)

These gaps often get filled as price returns to "fair value".
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class FVGType(Enum):
    """FVG type."""
    BULLISH = "bullish"  # Demand gap (unfilled buying)
    BEARISH = "bearish"  # Supply gap (unfilled selling)


class FVGStatus(Enum):
    """FVG status."""
    UNFILLED = "unfilled"  # Gap not yet filled
    PARTIALLY_FILLED = "partially_filled"  # Price partially retraced into gap
    FILLED = "filled"  # Gap completely filled
    EXPIRED = "expired"  # Too old, no longer relevant


@dataclass
class FairValueGap:
    """Fair Value Gap (FVG)."""
    fvg_id: str
    symbol: str
    fvg_type: FVGType
    gap_low: float
    gap_high: float
    created_at: datetime
    status: FVGStatus
    fill_percentage: float = 0  # 0-100%
    timeframe: str = '1m'

    @property
    def gap_size(self) -> float:
        """Gap size in price units."""
        return self.gap_high - self.gap_low

    @property
    def gap_mid(self) -> float:
        """Middle of gap."""
        return (self.gap_low + self.gap_high) / 2


class FairValueGapDetector:
    """
    Fair Value Gap (FVG) Detector.

    FVG Detection (3-candle pattern):

    Bullish FVG:
        Candle 1: Base candle
        Candle 2: Strong move up
        Candle 3: Continuation up
        Gap: Candle 1 High < Candle 3 Low (unfilled space)

    Bearish FVG:
        Candle 1: Base candle
        Candle 2: Strong move down
        Candle 3: Continuation down
        Gap: Candle 1 Low > Candle 3 High (unfilled space)

    Trading Logic:
    - Price often returns to fill FVGs
    - Fresh FVGs are highest priority
    - Partially filled FVGs can still provide support/resistance
    """

    def __init__(
        self,
        db_manager=None,
        min_gap_pct: float = 0.1,  # Min gap size as % of price
        max_age_hours: int = 24  # Max age before FVG expires
    ):
        """
        Initialize FVG Detector.

        Args:
            db_manager: Database manager for candle data
            min_gap_pct: Minimum gap size percentage
            max_age_hours: Maximum FVG age in hours
        """
        self.db_manager = db_manager
        self.min_gap_pct = min_gap_pct
        self.max_age_hours = max_age_hours

        # FVG storage per symbol
        self._fvgs: Dict[str, List[FairValueGap]] = {}

        logger.info(
            f"FairValueGapDetector initialized - "
            f"min_gap={min_gap_pct}%, max_age={max_age_hours}h"
        )

    async def identify_fvgs(
        self,
        symbol: str,
        timeframe: str = '1m',
        lookback_candles: int = 100
    ) -> List[FairValueGap]:
        """
        Identify Fair Value Gaps from recent candles.

        Args:
            symbol: Trading pair
            timeframe: Candle timeframe ('1m', '5m', '15m')
            lookback_candles: How many candles to analyze

        Returns:
            List of detected FVGs
        """
        candles = await self._get_candles(symbol, timeframe, lookback_candles)

        if len(candles) < 3:
            return []

        fvgs = []

        # Scan for 3-candle patterns
        for i in range(len(candles) - 2):
            candle_1 = candles[i]
            candle_2 = candles[i + 1]
            candle_3 = candles[i + 2]

            # Check for bullish FVG
            bullish_fvg = self._detect_bullish_fvg(candle_1, candle_2, candle_3)
            if bullish_fvg:
                fvg = FairValueGap(
                    fvg_id=f"{symbol}_bull_fvg_{i}_{datetime.utcnow().timestamp()}",
                    symbol=symbol,
                    fvg_type=FVGType.BULLISH,
                    gap_low=candle_1['high'],
                    gap_high=candle_3['low'],
                    created_at=candle_3['timestamp'],
                    status=FVGStatus.UNFILLED,
                    timeframe=timeframe
                )
                fvgs.append(fvg)
                logger.info(
                    f"Bullish FVG detected: {symbol} @ "
                    f"${fvg.gap_low:.2f} - ${fvg.gap_high:.2f} ({timeframe})"
                )

            # Check for bearish FVG
            bearish_fvg = self._detect_bearish_fvg(candle_1, candle_2, candle_3)
            if bearish_fvg:
                fvg = FairValueGap(
                    fvg_id=f"{symbol}_bear_fvg_{i}_{datetime.utcnow().timestamp()}",
                    symbol=symbol,
                    fvg_type=FVGType.BEARISH,
                    gap_low=candle_3['high'],
                    gap_high=candle_1['low'],
                    created_at=candle_3['timestamp'],
                    status=FVGStatus.UNFILLED,
                    timeframe=timeframe
                )
                fvgs.append(fvg)
                logger.info(
                    f"Bearish FVG detected: {symbol} @ "
                    f"${fvg.gap_low:.2f} - ${fvg.gap_high:.2f} ({timeframe})"
                )

        return fvgs

    def _detect_bullish_fvg(
        self,
        candle_1: Dict,
        candle_2: Dict,
        candle_3: Dict
    ) -> bool:
        """
        Detect bullish FVG pattern.

        Bullish FVG occurs when:
        - Candle 1 high < Candle 3 low (gap exists)
        - Candle 2 is bullish (up move)
        - Gap size meets minimum threshold

        Args:
            candle_1: First candle
            candle_2: Middle candle
            candle_3: Third candle

        Returns:
            True if bullish FVG detected
        """
        # Check if gap exists
        if candle_1['high'] >= candle_3['low']:
            return False

        # Check if middle candle is bullish
        if candle_2['close'] <= candle_2['open']:
            return False

        # Check gap size
        gap_size = candle_3['low'] - candle_1['high']
        avg_price = (candle_1['close'] + candle_2['close'] + candle_3['close']) / 3
        gap_pct = (gap_size / avg_price) * 100

        return gap_pct >= self.min_gap_pct

    def _detect_bearish_fvg(
        self,
        candle_1: Dict,
        candle_2: Dict,
        candle_3: Dict
    ) -> bool:
        """
        Detect bearish FVG pattern.

        Bearish FVG occurs when:
        - Candle 1 low > Candle 3 high (gap exists)
        - Candle 2 is bearish (down move)
        - Gap size meets minimum threshold

        Args:
            candle_1: First candle
            candle_2: Middle candle
            candle_3: Third candle

        Returns:
            True if bearish FVG detected
        """
        # Check if gap exists
        if candle_1['low'] <= candle_3['high']:
            return False

        # Check if middle candle is bearish
        if candle_2['close'] >= candle_2['open']:
            return False

        # Check gap size
        gap_size = candle_1['low'] - candle_3['high']
        avg_price = (candle_1['close'] + candle_2['close'] + candle_3['close']) / 3
        gap_pct = (gap_size / avg_price) * 100

        return gap_pct >= self.min_gap_pct

    async def track_fill_percentage(
        self,
        symbol: str,
        current_price: float
    ):
        """
        Track fill percentage of all FVGs.

        Updates:
        - Fill percentage (how much price retraced into gap)
        - Status (unfilled -> partially filled -> filled)
        - Remove filled or expired FVGs

        Args:
            symbol: Trading pair
            current_price: Current market price
        """
        if symbol not in self._fvgs:
            return

        fvgs_to_remove = []

        for fvg in self._fvgs[symbol]:
            # Check if FVG is expired
            age_hours = (datetime.utcnow() - fvg.created_at).total_seconds() / 3600
            if age_hours > self.max_age_hours:
                fvg.status = FVGStatus.EXPIRED
                fvgs_to_remove.append(fvg)
                logger.debug(f"FVG expired: {fvg.fvg_id}")
                continue

            # Calculate fill percentage
            if fvg.fvg_type == FVGType.BULLISH:
                # Bullish FVG fills when price comes down
                if current_price >= fvg.gap_high:
                    fill_pct = 0  # Above gap, not filled
                elif current_price <= fvg.gap_low:
                    fill_pct = 100  # Below gap, fully filled
                else:
                    # Partially filled
                    fill_pct = ((fvg.gap_high - current_price) / fvg.gap_size) * 100

            else:  # Bearish FVG
                # Bearish FVG fills when price comes up
                if current_price <= fvg.gap_low:
                    fill_pct = 0  # Below gap, not filled
                elif current_price >= fvg.gap_high:
                    fill_pct = 100  # Above gap, fully filled
                else:
                    # Partially filled
                    fill_pct = ((current_price - fvg.gap_low) / fvg.gap_size) * 100

            # Update fill percentage
            fvg.fill_percentage = fill_pct

            # Update status
            if fill_pct >= 100:
                fvg.status = FVGStatus.FILLED
                fvgs_to_remove.append(fvg)
                logger.info(f"FVG filled: {fvg.fvg_id}")
            elif fill_pct > 0:
                fvg.status = FVGStatus.PARTIALLY_FILLED
            else:
                fvg.status = FVGStatus.UNFILLED

        # Remove filled/expired FVGs
        for fvg in fvgs_to_remove:
            self._fvgs[symbol].remove(fvg)

    async def get_unfilled_fvgs(
        self,
        symbol: str,
        fvg_type: Optional[FVGType] = None
    ) -> List[FairValueGap]:
        """
        Get unfilled or partially filled FVGs.

        Args:
            symbol: Trading pair
            fvg_type: Filter by type (bullish/bearish) or None for all

        Returns:
            List of unfilled/partially filled FVGs
        """
        if symbol not in self._fvgs:
            return []

        fvgs = self._fvgs[symbol]

        # Filter by status
        active_fvgs = [
            fvg for fvg in fvgs
            if fvg.status in (FVGStatus.UNFILLED, FVGStatus.PARTIALLY_FILLED)
        ]

        # Filter by type if specified
        if fvg_type:
            active_fvgs = [fvg for fvg in active_fvgs if fvg.fvg_type == fvg_type]

        # Sort by creation time (newest first)
        active_fvgs.sort(key=lambda x: x.created_at, reverse=True)

        return active_fvgs

    def add_fvg(self, symbol: str, fvg: FairValueGap):
        """Add an FVG to tracking."""
        if symbol not in self._fvgs:
            self._fvgs[symbol] = []

        self._fvgs[symbol].append(fvg)

    async def _get_candles(
        self,
        symbol: str,
        timeframe: str,
        lookback: int
    ) -> List[Dict[str, Any]]:
        """Get candles from database or cache."""
        # In production, query from DuckDB
        # For now, return empty (placeholder)
        return []


# Example usage and testing
async def test_fvg_detector():
    """Test Fair Value Gap detector."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    detector = FairValueGapDetector(
        min_gap_pct=0.1,
        max_age_hours=24
    )

    print("="*60)
    print("FAIR VALUE GAP DETECTION TEST")
    print("="*60)

    symbol = 'BTCUSDT'

    # Create a bullish FVG manually
    bullish_fvg = FairValueGap(
        fvg_id=f"{symbol}_bull_fvg_1",
        symbol=symbol,
        fvg_type=FVGType.BULLISH,
        gap_low=94500,  # Candle 1 high
        gap_high=94800,  # Candle 3 low
        created_at=datetime.utcnow(),
        status=FVGStatus.UNFILLED,
        timeframe='5m'
    )
    detector.add_fvg(symbol, bullish_fvg)

    # Create a bearish FVG manually
    bearish_fvg = FairValueGap(
        fvg_id=f"{symbol}_bear_fvg_1",
        symbol=symbol,
        fvg_type=FVGType.BEARISH,
        gap_low=95200,  # Candle 3 high
        gap_high=95500,  # Candle 1 low
        created_at=datetime.utcnow(),
        status=FVGStatus.UNFILLED,
        timeframe='5m'
    )
    detector.add_fvg(symbol, bearish_fvg)

    print(f"\nFVGs created for {symbol}:")
    print(f"  Bullish FVG: ${bullish_fvg.gap_low:.0f} - ${bullish_fvg.gap_high:.0f} (size: ${bullish_fvg.gap_size:.0f})")
    print(f"  Bearish FVG: ${bearish_fvg.gap_low:.0f} - ${bearish_fvg.gap_high:.0f} (size: ${bearish_fvg.gap_size:.0f})")

    # Test fill tracking - price at $95,000
    current_price = 95000
    print(f"\nCurrent price: ${current_price:,.0f}")

    await detector.track_fill_percentage(symbol, current_price)

    print(f"\nFVG Status After Price Update:")
    print(f"  Bullish FVG: {bullish_fvg.status.value} (fill: {bullish_fvg.fill_percentage:.1f}%)")
    print(f"  Bearish FVG: {bearish_fvg.status.value} (fill: {bearish_fvg.fill_percentage:.1f}%)")

    # Test price filling bullish FVG
    print(f"\nPrice retraces to fill bullish FVG: $94,600")
    await detector.track_fill_percentage(symbol, 94600)
    print(f"  Bullish FVG fill: {bullish_fvg.fill_percentage:.1f}% ({bullish_fvg.status.value})")

    # Get unfilled FVGs
    unfilled = await detector.get_unfilled_fvgs(symbol)
    print(f"\nUnfilled/Partially Filled FVGs: {len(unfilled)}")
    for fvg in unfilled:
        print(f"  {fvg.fvg_type.value}: ${fvg.gap_low:.0f}-${fvg.gap_high:.0f} ({fvg.status.value}, {fvg.fill_percentage:.1f}%)")

    print("\n" + "="*60)


if __name__ == "__main__":
    asyncio.run(test_fvg_detector())
