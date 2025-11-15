"""
Supply/Demand Zone Detector - Identify and track support/resistance zones.

Detects:
1. Demand zones (support) - Areas where buying pressure emerged
2. Supply zones (resistance) - Areas where selling pressure emerged
3. Zone status tracking - Fresh, Tested, Broken
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ZoneStatus(Enum):
    """Zone status."""
    FRESH = "fresh"  # Never tested
    TESTED = "tested"  # Price touched but held
    BROKEN = "broken"  # Price broke through
    WEAK = "weak"  # Multiple tests, losing strength


@dataclass
class Zone:
    """Supply or Demand zone."""
    zone_id: str
    zone_type: str  # 'demand' or 'supply'
    price_low: float
    price_high: float
    created_at: datetime
    status: ZoneStatus
    strength: float  # 0-100 score
    test_count: int = 0
    last_test_time: Optional[datetime] = None
    origin_candles: int = 1  # Number of candles in base
    volume_at_origin: float = 0

    @property
    def price_mid(self) -> float:
        """Middle price of zone."""
        return (self.price_low + self.price_high) / 2

    @property
    def zone_width(self) -> float:
        """Width of zone in price units."""
        return self.price_high - self.price_low


class SupplyDemandDetector:
    """
    Supply/Demand Zone Detector.

    Methodology:
    - Demand Zone: Area where strong buying emerged (price rallied sharply from level)
    - Supply Zone: Area where strong selling emerged (price dropped sharply from level)

    Detection Criteria:
    1. Basing period (consolidation at level)
    2. Sharp move away from level (breakout)
    3. Strong volume (confirmation)

    Zone Strength Factors:
    - Time spent at level (longer = stronger)
    - Volume (higher = stronger)
    - Number of touches (fewer = stronger, fresh zones best)
    - Distance from current price (closer = more relevant)
    """

    def __init__(
        self,
        db_manager=None,
        min_base_candles: int = 3,  # Min candles in consolidation
        min_breakout_pct: float = 0.5,  # Min % move for valid breakout
        max_zones: int = 50  # Max zones to track per symbol
    ):
        """
        Initialize Supply/Demand Detector.

        Args:
            db_manager: Database manager for candle data
            min_base_candles: Minimum candles in basing period
            min_breakout_pct: Minimum breakout move percentage
            max_zones: Maximum zones to track per symbol
        """
        self.db_manager = db_manager
        self.min_base_candles = min_base_candles
        self.min_breakout_pct = min_breakout_pct
        self.max_zones = max_zones

        # Zone storage per symbol
        self._zones: Dict[str, List[Zone]] = {}

        logger.info(
            f"SupplyDemandDetector initialized - "
            f"min_base_candles={min_base_candles}, min_breakout={min_breakout_pct}%"
        )

    async def identify_demand_zones(
        self,
        symbol: str,
        lookback_candles: int = 100
    ) -> List[Zone]:
        """
        Identify demand zones (support levels).

        Demand Zone Pattern:
        1. Price consolidates at level (basing)
        2. Strong rally away from level (breakout up)
        3. Zone = consolidation range

        Args:
            symbol: Trading pair
            lookback_candles: How many candles to analyze

        Returns:
            List of demand zones
        """
        candles = await self._get_candles(symbol, lookback_candles)

        if len(candles) < self.min_base_candles + 5:
            return []

        demand_zones = []

        # Scan for base + breakout patterns
        for i in range(len(candles) - self.min_base_candles - 1):
            # Check if we have a consolidation (base)
            base_candles = candles[i:i + self.min_base_candles]
            breakout_candle = candles[i + self.min_base_candles]

            base_high = max(c['high'] for c in base_candles)
            base_low = min(c['low'] for c in base_candles)
            base_range = base_high - base_low

            # Check for tight consolidation
            avg_price = sum(c['close'] for c in base_candles) / len(base_candles)
            if base_range / avg_price > 0.02:  # Max 2% range
                continue

            # Check for breakout up
            breakout_move = (breakout_candle['close'] - base_high) / base_high * 100

            if breakout_move >= self.min_breakout_pct:
                # Valid demand zone found
                zone = Zone(
                    zone_id=f"{symbol}_demand_{i}_{datetime.utcnow().timestamp()}",
                    zone_type='demand',
                    price_low=base_low,
                    price_high=base_high,
                    created_at=base_candles[0]['timestamp'],
                    status=ZoneStatus.FRESH,
                    strength=self._calculate_zone_strength(base_candles, breakout_move),
                    origin_candles=len(base_candles),
                    volume_at_origin=sum(c['volume'] for c in base_candles)
                )

                demand_zones.append(zone)
                logger.info(
                    f"Demand zone identified: {symbol} @ ${zone.price_mid:.2f} "
                    f"(strength: {zone.strength:.0f})"
                )

        return demand_zones

    async def identify_supply_zones(
        self,
        symbol: str,
        lookback_candles: int = 100
    ) -> List[Zone]:
        """
        Identify supply zones (resistance levels).

        Supply Zone Pattern:
        1. Price consolidates at level (basing)
        2. Strong drop away from level (breakout down)
        3. Zone = consolidation range

        Args:
            symbol: Trading pair
            lookback_candles: How many candles to analyze

        Returns:
            List of supply zones
        """
        candles = await self._get_candles(symbol, lookback_candles)

        if len(candles) < self.min_base_candles + 5:
            return []

        supply_zones = []

        for i in range(len(candles) - self.min_base_candles - 1):
            base_candles = candles[i:i + self.min_base_candles]
            breakout_candle = candles[i + self.min_base_candles]

            base_high = max(c['high'] for c in base_candles)
            base_low = min(c['low'] for c in base_candles)
            base_range = base_high - base_low

            avg_price = sum(c['close'] for c in base_candles) / len(base_candles)
            if base_range / avg_price > 0.02:
                continue

            # Check for breakout down
            breakout_move = abs((breakout_candle['close'] - base_low) / base_low * 100)

            if breakout_move >= self.min_breakout_pct and breakout_candle['close'] < base_low:
                zone = Zone(
                    zone_id=f"{symbol}_supply_{i}_{datetime.utcnow().timestamp()}",
                    zone_type='supply',
                    price_low=base_low,
                    price_high=base_high,
                    created_at=base_candles[0]['timestamp'],
                    status=ZoneStatus.FRESH,
                    strength=self._calculate_zone_strength(base_candles, breakout_move),
                    origin_candles=len(base_candles),
                    volume_at_origin=sum(c['volume'] for c in base_candles)
                )

                supply_zones.append(zone)
                logger.info(
                    f"Supply zone identified: {symbol} @ ${zone.price_mid:.2f} "
                    f"(strength: {zone.strength:.0f})"
                )

        return supply_zones

    def _calculate_zone_strength(
        self,
        base_candles: List[Dict],
        breakout_move_pct: float
    ) -> float:
        """
        Calculate zone strength score (0-100).

        Factors:
        - Base duration (more candles = stronger)
        - Breakout strength (larger move = stronger)
        - Volume (higher volume = stronger)

        Args:
            base_candles: Candles in consolidation
            breakout_move_pct: Breakout move percentage

        Returns:
            Strength score 0-100
        """
        # Base duration score (0-40 points)
        duration_score = min(len(base_candles) * 8, 40)

        # Breakout strength score (0-40 points)
        breakout_score = min(breakout_move_pct * 8, 40)

        # Volume score (0-20 points)
        avg_volume = sum(c['volume'] for c in base_candles) / len(base_candles)
        volume_score = min(avg_volume / 100, 20)  # Simplified

        total_score = duration_score + breakout_score + volume_score

        return min(total_score, 100)

    async def update_zone_status(
        self,
        symbol: str,
        current_price: float
    ):
        """
        Update zone status based on current price.

        Updates:
        - Test count (if price touches zone)
        - Status (fresh -> tested -> broken)
        - Remove broken zones

        Args:
            symbol: Trading pair
            current_price: Current market price
        """
        if symbol not in self._zones:
            return

        zones_to_remove = []

        for zone in self._zones[symbol]:
            # Check if price is testing the zone
            if zone.price_low <= current_price <= zone.price_high:
                zone.test_count += 1
                zone.last_test_time = datetime.utcnow()

                if zone.status == ZoneStatus.FRESH:
                    zone.status = ZoneStatus.TESTED
                    logger.info(f"Zone tested: {zone.zone_id}")
                elif zone.test_count >= 3:
                    zone.status = ZoneStatus.WEAK
                    logger.info(f"Zone weakened: {zone.zone_id}")

            # Check if zone is broken
            if zone.zone_type == 'demand' and current_price < zone.price_low:
                zone.status = ZoneStatus.BROKEN
                zones_to_remove.append(zone)
                logger.info(f"Demand zone broken: {zone.zone_id}")

            elif zone.zone_type == 'supply' and current_price > zone.price_high:
                zone.status = ZoneStatus.BROKEN
                zones_to_remove.append(zone)
                logger.info(f"Supply zone broken: {zone.zone_id}")

        # Remove broken zones
        for zone in zones_to_remove:
            self._zones[symbol].remove(zone)

    async def get_nearest_zones(
        self,
        symbol: str,
        current_price: Optional[float] = None
    ) -> Dict[str, Optional[Zone]]:
        """
        Get nearest demand and supply zones to current price.

        Args:
            symbol: Trading pair
            current_price: Current price (optional)

        Returns:
            Dict with 'demand' and 'supply' nearest zones
        """
        if symbol not in self._zones or not self._zones[symbol]:
            return {'demand': None, 'supply': None}

        zones = self._zones[symbol]

        # Filter valid zones
        demand_zones = [z for z in zones if z.zone_type == 'demand' and z.status != ZoneStatus.BROKEN]
        supply_zones = [z for z in zones if z.zone_type == 'supply' and z.status != ZoneStatus.BROKEN]

        result = {'demand': None, 'supply': None}

        # Find nearest demand zone (below price)
        if demand_zones and current_price:
            demand_below = [z for z in demand_zones if z.price_high < current_price]
            if demand_below:
                result['demand'] = max(demand_below, key=lambda z: z.price_high)

        # Find nearest supply zone (above price)
        if supply_zones and current_price:
            supply_above = [z for z in supply_zones if z.price_low > current_price]
            if supply_above:
                result['supply'] = min(supply_above, key=lambda z: z.price_low)

        return result

    def add_zone(self, symbol: str, zone: Zone):
        """Add a zone to tracking."""
        if symbol not in self._zones:
            self._zones[symbol] = []

        self._zones[symbol].append(zone)

        # Limit zone count
        if len(self._zones[symbol]) > self.max_zones:
            # Remove oldest or weakest
            self._zones[symbol].sort(key=lambda z: (z.strength, z.created_at), reverse=True)
            self._zones[symbol] = self._zones[symbol][:self.max_zones]

    async def _get_candles(
        self,
        symbol: str,
        lookback: int
    ) -> List[Dict[str, Any]]:
        """Get candles from database or cache."""
        # In production, query from DuckDB
        # For now, return empty (placeholder)
        return []


# Example usage and testing
async def test_supply_demand():
    """Test supply/demand zone detector."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    detector = SupplyDemandDetector(
        min_base_candles=3,
        min_breakout_pct=0.5
    )

    print("="*60)
    print("SUPPLY/DEMAND ZONE DETECTION TEST")
    print("="*60)

    # Create sample zones manually
    symbol = 'BTCUSDT'

    # Demand zone at $94,000
    demand_zone = Zone(
        zone_id=f"{symbol}_demand_1",
        zone_type='demand',
        price_low=94000,
        price_high=94200,
        created_at=datetime.utcnow(),
        status=ZoneStatus.FRESH,
        strength=85,
        origin_candles=5,
        volume_at_origin=1000
    )
    detector.add_zone(symbol, demand_zone)

    # Supply zone at $96,000
    supply_zone = Zone(
        zone_id=f"{symbol}_supply_1",
        zone_type='supply',
        price_low=96000,
        price_high=96200,
        created_at=datetime.utcnow(),
        status=ZoneStatus.FRESH,
        strength=75,
        origin_candles=4,
        volume_at_origin=800
    )
    detector.add_zone(symbol, supply_zone)

    print(f"\nZones added for {symbol}:")
    print(f"  Demand Zone: ${demand_zone.price_low:.0f} - ${demand_zone.price_high:.0f} (strength: {demand_zone.strength:.0f})")
    print(f"  Supply Zone: ${supply_zone.price_low:.0f} - ${supply_zone.price_high:.0f} (strength: {supply_zone.strength:.0f})")

    # Test nearest zones
    current_price = 95000
    print(f"\nCurrent price: ${current_price:,.0f}")

    nearest = await detector.get_nearest_zones(symbol, current_price)
    print("\nNearest zones:")
    if nearest['demand']:
        print(f"  Nearest Demand: ${nearest['demand'].price_mid:.0f} (status: {nearest['demand'].status.value})")
    if nearest['supply']:
        print(f"  Nearest Supply: ${nearest['supply'].price_mid:.0f} (status: {nearest['supply'].status.value})")

    # Test zone update (price tests demand)
    print(f"\nPrice moves to test demand zone: $94,100")
    await detector.update_zone_status(symbol, 94100)
    print(f"  Demand zone status: {demand_zone.status.value}")
    print(f"  Test count: {demand_zone.test_count}")

    print("\n" + "="*60)


if __name__ == "__main__":
    asyncio.run(test_supply_demand())
