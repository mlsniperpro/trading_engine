"""
Market Profile Analyzer - POC, VAH, VAL calculations.

Calculates:
1. POC (Point of Control) - Price with highest volume
2. VAH (Value Area High) - Top of 70% volume area
3. VAL (Value Area Low) - Bottom of 70% volume area
4. Volume distribution histogram
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class PriceLevel:
    """Represents a price level with volume."""
    price: float
    volume: float
    buy_volume: float = 0
    sell_volume: float = 0


@dataclass
class MarketProfile:
    """Market profile result."""
    symbol: str
    poc: float  # Point of Control
    vah: float  # Value Area High
    val: float  # Value Area Low
    total_volume: float
    value_area_volume: float
    price_levels: List[PriceLevel]
    timeframe: str
    timestamp: datetime


class MarketProfileAnalyzer:
    """
    Market Profile Analyzer - Calculates POC, VAH, VAL.

    Market Profile Concepts:
    - POC (Point of Control): Price level with highest traded volume
    - Value Area: Range where 70% of volume was traded
    - VAH (Value Area High): Upper bound of value area
    - VAL (Value Area Low): Lower bound of value area

    Calculation Process:
    1. Group trades by price level
    2. Calculate volume at each price level
    3. Find POC (highest volume price)
    4. Build value area by adding prices with most volume until 70% reached
    5. VAH = highest price in value area, VAL = lowest price in value area
    """

    def __init__(
        self,
        db_manager=None,
        tick_size: float = 0.01,  # Group prices by this increment
        value_area_pct: float = 0.70  # 70% of volume
    ):
        """
        Initialize Market Profile Analyzer.

        Args:
            db_manager: Database manager for querying ticks
            tick_size: Price grouping increment (e.g., $0.01)
            value_area_pct: Percentage of volume for value area (0.70 = 70%)
        """
        self.db_manager = db_manager
        self.tick_size = tick_size
        self.value_area_pct = value_area_pct

        # In-memory cache for testing
        self._tick_cache: Dict[str, List[Dict[str, Any]]] = {}

        logger.info(
            f"MarketProfileAnalyzer initialized - "
            f"tick_size=${tick_size}, value_area={value_area_pct*100}%"
        )

    async def calculate_profile(
        self,
        symbol: str,
        timeframe: str = '15m'
    ) -> Dict[str, Any]:
        """
        Calculate market profile (POC, VAH, VAL).

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            timeframe: Timeframe to analyze ('1m', '5m', '15m')

        Returns:
            Dict with poc, vah, val, volume_distribution
        """
        # Get lookback period based on timeframe
        lookback_seconds = self._get_lookback_seconds(timeframe)

        # Get trade ticks
        ticks = await self._get_ticks(symbol, lookback_seconds)

        if not ticks:
            return {
                'poc': None,
                'vah': None,
                'val': None,
                'total_volume': 0,
                'value_area_volume': 0,
                'price_levels': [],
                'timeframe': timeframe,
                'timestamp': datetime.utcnow()
            }

        # Build volume profile
        volume_profile = self._build_volume_profile(ticks)

        # Calculate POC
        poc_price, poc_volume = self._calculate_poc(volume_profile)

        # Calculate Value Area (VAH, VAL)
        vah, val, value_area_volume = self._calculate_value_area(
            volume_profile,
            poc_price
        )

        # Total volume
        total_volume = sum(level.volume for level in volume_profile.values())

        result = {
            'poc': poc_price,
            'vah': vah,
            'val': val,
            'total_volume': total_volume,
            'value_area_volume': value_area_volume,
            'price_levels': list(volume_profile.values()),
            'timeframe': timeframe,
            'timestamp': datetime.utcnow()
        }

        logger.debug(
            f"Market Profile for {symbol} ({timeframe}): "
            f"POC=${poc_price:.2f}, VAH=${vah:.2f}, VAL=${val:.2f}"
        )

        return result

    def _build_volume_profile(
        self,
        ticks: List[Dict[str, Any]]
    ) -> Dict[float, PriceLevel]:
        """
        Build volume profile from ticks.

        Args:
            ticks: List of trade ticks

        Returns:
            Dict mapping price level to PriceLevel object
        """
        profile: Dict[float, PriceLevel] = defaultdict(
            lambda: PriceLevel(price=0, volume=0, buy_volume=0, sell_volume=0)
        )

        for tick in ticks:
            # Round price to tick size
            price = self._round_to_tick(tick['price'])
            amount = tick['amount']
            side = tick.get('side', 'buy')

            # Update price level
            if profile[price].price == 0:
                profile[price].price = price

            profile[price].volume += amount

            if side == 'buy':
                profile[price].buy_volume += amount
            else:
                profile[price].sell_volume += amount

        return dict(profile)

    def _calculate_poc(
        self,
        volume_profile: Dict[float, PriceLevel]
    ) -> Tuple[float, float]:
        """
        Calculate Point of Control (price with highest volume).

        Args:
            volume_profile: Volume profile dict

        Returns:
            Tuple of (poc_price, poc_volume)
        """
        if not volume_profile:
            return 0, 0

        # Find price level with max volume
        poc_level = max(volume_profile.values(), key=lambda x: x.volume)

        return poc_level.price, poc_level.volume

    def _calculate_value_area(
        self,
        volume_profile: Dict[float, PriceLevel],
        poc_price: float
    ) -> Tuple[float, float, float]:
        """
        Calculate Value Area High (VAH) and Value Area Low (VAL).

        Process:
        1. Start at POC
        2. Add adjacent price levels with most volume
        3. Continue until 70% of total volume is included
        4. VAH = highest price in area, VAL = lowest price in area

        Args:
            volume_profile: Volume profile dict
            poc_price: Point of Control price

        Returns:
            Tuple of (vah, val, value_area_volume)
        """
        if not volume_profile:
            return 0, 0, 0

        # Calculate total volume
        total_volume = sum(level.volume for level in volume_profile.values())
        target_volume = total_volume * self.value_area_pct

        # Sort price levels by price
        sorted_prices = sorted(volume_profile.keys())

        # Find POC index
        poc_index = sorted_prices.index(poc_price) if poc_price in sorted_prices else len(sorted_prices) // 2

        # Build value area starting from POC
        value_area_prices = {poc_price}
        accumulated_volume = volume_profile[poc_price].volume

        # Indices for expanding area
        upper_index = poc_index + 1
        lower_index = poc_index - 1

        # Expand value area until we reach target volume
        while accumulated_volume < target_volume:
            # Determine which direction to expand
            upper_volume = volume_profile[sorted_prices[upper_index]].volume if upper_index < len(sorted_prices) else 0
            lower_volume = volume_profile[sorted_prices[lower_index]].volume if lower_index >= 0 else 0

            if upper_volume == 0 and lower_volume == 0:
                break  # No more prices to add

            # Add the price level with higher volume
            if upper_volume >= lower_volume and upper_index < len(sorted_prices):
                price = sorted_prices[upper_index]
                value_area_prices.add(price)
                accumulated_volume += upper_volume
                upper_index += 1
            elif lower_index >= 0:
                price = sorted_prices[lower_index]
                value_area_prices.add(price)
                accumulated_volume += lower_volume
                lower_index -= 1
            else:
                break

        # VAH and VAL
        vah = max(value_area_prices) if value_area_prices else poc_price
        val = min(value_area_prices) if value_area_prices else poc_price

        return vah, val, accumulated_volume

    def get_volume_distribution(
        self,
        profile: Dict[str, Any]
    ) -> List[Tuple[float, float]]:
        """
        Get volume distribution as price-volume pairs.

        Args:
            profile: Market profile result

        Returns:
            List of (price, volume) tuples sorted by price
        """
        price_levels = profile.get('price_levels', [])
        distribution = [(level.price, level.volume) for level in price_levels]
        return sorted(distribution, key=lambda x: x[0])

    def _round_to_tick(self, price: float) -> float:
        """Round price to nearest tick size."""
        return round(price / self.tick_size) * self.tick_size

    def _get_lookback_seconds(self, timeframe: str) -> int:
        """Get lookback period in seconds for a timeframe."""
        timeframe_map = {
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '30m': 1800,
            '1h': 3600
        }
        return timeframe_map.get(timeframe, 900)  # Default: 15m

    async def _get_ticks(
        self,
        symbol: str,
        lookback_seconds: int
    ) -> List[Dict[str, Any]]:
        """
        Get trade ticks from database or cache.

        Args:
            symbol: Trading pair
            lookback_seconds: How far back to look

        Returns:
            List of tick dicts
        """
        # If DB manager available, query from DuckDB
        if self.db_manager:
            # In production: SELECT * FROM ticks WHERE timestamp > NOW() - INTERVAL ...
            pass

        # For now, use in-memory cache
        if symbol in self._tick_cache:
            cutoff_time = datetime.utcnow() - timedelta(seconds=lookback_seconds)
            return [
                tick for tick in self._tick_cache[symbol]
                if tick['timestamp'] >= cutoff_time
            ]

        return []

    def add_tick(self, symbol: str, tick: Dict[str, Any]):
        """Add a tick to cache (for testing)."""
        if symbol not in self._tick_cache:
            self._tick_cache[symbol] = []

        self._tick_cache[symbol].append(tick)

        # Keep only last 15 minutes
        cutoff_time = datetime.utcnow() - timedelta(minutes=15)
        self._tick_cache[symbol] = [
            t for t in self._tick_cache[symbol]
            if t['timestamp'] >= cutoff_time
        ]


# Example usage and testing
async def test_market_profile():
    """Test market profile analyzer with sample data."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    analyzer = MarketProfileAnalyzer(tick_size=1.0)

    # Generate sample ticks with volume concentration
    symbol = 'BTCUSDT'
    now = datetime.utcnow()

    # Create a normal distribution of prices around $95,000
    # POC should be around $95,000
    import random
    random.seed(42)

    for i in range(1000):
        # Normal distribution centered at 95000
        price = random.gauss(95000, 100)
        amount = random.uniform(0.01, 0.5)
        side = random.choice(['buy', 'sell'])

        tick = {
            'price': price,
            'amount': amount,
            'side': side,
            'timestamp': now - timedelta(seconds=900 - i)
        }
        analyzer.add_tick(symbol, tick)

    # Calculate market profile
    print("\n" + "="*60)
    print("MARKET PROFILE CALCULATION TEST")
    print("="*60)

    profile = await analyzer.calculate_profile(symbol, timeframe='15m')

    print(f"POC (Point of Control): ${profile['poc']:,.2f}")
    print(f"VAH (Value Area High):  ${profile['vah']:,.2f}")
    print(f"VAL (Value Area Low):   ${profile['val']:,.2f}")
    print(f"Total Volume: {profile['total_volume']:,.2f}")
    print(f"Value Area Volume: {profile['value_area_volume']:,.2f}")
    print(f"Value Area %: {(profile['value_area_volume']/profile['total_volume']*100):.1f}%")

    # Show volume distribution
    print("\nVolume Distribution (top 10 levels):")
    price_levels = sorted(profile['price_levels'], key=lambda x: x.volume, reverse=True)[:10]
    for level in price_levels:
        print(f"  ${level.price:,.2f}: {level.volume:.2f} (Buy: {level.buy_volume:.2f}, Sell: {level.sell_volume:.2f})")


if __name__ == "__main__":
    asyncio.run(test_market_profile())
