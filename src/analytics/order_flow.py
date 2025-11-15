"""
Order Flow Analyzer - CVD, imbalances, and whale detection.

Calculates:
1. Cumulative Volume Delta (CVD) - net buying/selling pressure
2. Order flow imbalances - buy/sell ratio detection
3. Large trades (whale detection)
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class TradeTick:
    """Represents a single trade tick."""
    symbol: str
    price: float
    amount: float
    side: str  # 'buy' or 'sell'
    timestamp: datetime
    exchange: str = 'binance'


@dataclass
class CVDResult:
    """CVD calculation result."""
    cvd: float
    trend: str  # 'bullish', 'bearish', 'neutral'
    buy_volume: float
    sell_volume: float
    net_volume: float
    lookback_seconds: int
    timestamp: datetime


@dataclass
class ImbalanceResult:
    """Order flow imbalance result."""
    buy_sell_ratio: float
    imbalance_detected: bool
    direction: str  # 'buy', 'sell', 'neutral'
    buy_volume: float
    sell_volume: float
    window_seconds: int
    timestamp: datetime


class OrderFlowAnalyzer:
    """
    Order Flow Analyzer - Calculates CVD and detects imbalances.

    CVD (Cumulative Volume Delta):
        CVD = Σ(Buy Volume - Sell Volume)
        - Positive CVD = More buying pressure
        - Negative CVD = More selling pressure

    Imbalance Detection:
        Ratio = Buy Volume / Sell Volume
        - Ratio > 2.5 = Strong buying imbalance
        - Ratio < 0.4 (1/2.5) = Strong selling imbalance
    """

    def __init__(
        self,
        db_manager=None,
        imbalance_threshold: float = 2.5,
        large_trade_threshold_usd: float = 50000
    ):
        """
        Initialize Order Flow Analyzer.

        Args:
            db_manager: Database manager for querying ticks
            imbalance_threshold: Ratio threshold for detecting imbalances
            large_trade_threshold_usd: USD value threshold for whale trades
        """
        self.db_manager = db_manager
        self.imbalance_threshold = imbalance_threshold
        self.large_trade_threshold = large_trade_threshold_usd

        # In-memory cache for testing (when no DB)
        self._tick_cache: Dict[str, List[TradeTick]] = {}

        logger.info(
            f"OrderFlowAnalyzer initialized - "
            f"imbalance_threshold={imbalance_threshold}, "
            f"large_trade_threshold=${large_trade_threshold_usd:,.0f}"
        )

    async def calculate_cvd(
        self,
        symbol: str,
        lookback_seconds: int = 300
    ) -> Dict[str, Any]:
        """
        Calculate Cumulative Volume Delta (CVD).

        CVD = Σ(Buy Volume - Sell Volume)

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            lookback_seconds: How many seconds to look back (default: 300 = 5 min)

        Returns:
            Dict with cvd, trend, buy_volume, sell_volume
        """
        # Get trade ticks
        ticks = await self._get_ticks(symbol, lookback_seconds)

        if not ticks:
            return {
                'cvd': 0,
                'trend': 'neutral',
                'buy_volume': 0,
                'sell_volume': 0,
                'net_volume': 0,
                'lookback_seconds': lookback_seconds,
                'timestamp': datetime.utcnow()
            }

        # Calculate volumes
        buy_volume = sum(t.amount for t in ticks if t.side == 'buy')
        sell_volume = sum(t.amount for t in ticks if t.side == 'sell')
        net_volume = buy_volume - sell_volume

        # CVD is cumulative - in production, this would be a running total
        # For now, we calculate over the lookback window
        cvd = net_volume

        # Determine trend
        if cvd > 0:
            if cvd > buy_volume * 0.3:  # Strong bullish
                trend = 'bullish'
            else:
                trend = 'neutral'
        elif cvd < 0:
            if abs(cvd) > sell_volume * 0.3:  # Strong bearish
                trend = 'bearish'
            else:
                trend = 'neutral'
        else:
            trend = 'neutral'

        result = {
            'cvd': cvd,
            'trend': trend,
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'net_volume': net_volume,
            'lookback_seconds': lookback_seconds,
            'timestamp': datetime.utcnow()
        }

        logger.debug(
            f"CVD for {symbol}: {cvd:.2f} ({trend}) - "
            f"Buy: {buy_volume:.2f}, Sell: {sell_volume:.2f}"
        )

        return result

    async def detect_imbalance(
        self,
        symbol: str,
        window_seconds: int = 30
    ) -> Dict[str, Any]:
        """
        Detect order flow imbalance (buy/sell ratio).

        Imbalance Ratio = Buy Volume / Sell Volume
        - Ratio > 2.5 = Strong buying imbalance
        - Ratio < 0.4 = Strong selling imbalance

        Args:
            symbol: Trading pair
            window_seconds: Time window to analyze (default: 30 sec)

        Returns:
            Dict with buy_sell_ratio, imbalance_detected, direction
        """
        ticks = await self._get_ticks(symbol, window_seconds)

        if not ticks:
            return {
                'buy_sell_ratio': 1.0,
                'imbalance_detected': False,
                'direction': 'neutral',
                'buy_volume': 0,
                'sell_volume': 0,
                'window_seconds': window_seconds,
                'timestamp': datetime.utcnow()
            }

        buy_volume = sum(t.amount for t in ticks if t.side == 'buy')
        sell_volume = sum(t.amount for t in ticks if t.side == 'sell')

        # Prevent division by zero
        if sell_volume == 0:
            ratio = float('inf') if buy_volume > 0 else 1.0
        else:
            ratio = buy_volume / sell_volume

        # Detect imbalance
        imbalance_detected = False
        direction = 'neutral'

        if ratio >= self.imbalance_threshold:
            imbalance_detected = True
            direction = 'buy'
        elif ratio <= (1.0 / self.imbalance_threshold):
            imbalance_detected = True
            direction = 'sell'

        result = {
            'buy_sell_ratio': ratio,
            'imbalance_detected': imbalance_detected,
            'direction': direction,
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'window_seconds': window_seconds,
            'timestamp': datetime.utcnow()
        }

        if imbalance_detected:
            logger.info(
                f"⚡ IMBALANCE detected for {symbol}: "
                f"{direction.upper()} - Ratio: {ratio:.2f}x"
            )

        return result

    async def detect_large_trades(
        self,
        symbol: str,
        lookback_seconds: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Detect large trades (whale detection).

        Args:
            symbol: Trading pair
            lookback_seconds: Time window to check (default: 60 sec)

        Returns:
            List of large trades with details
        """
        ticks = await self._get_ticks(symbol, lookback_seconds)

        large_trades = []

        for tick in ticks:
            # Calculate USD value
            usd_value = tick.price * tick.amount

            if usd_value >= self.large_trade_threshold:
                large_trades.append({
                    'symbol': tick.symbol,
                    'price': tick.price,
                    'amount': tick.amount,
                    'usd_value': usd_value,
                    'side': tick.side,
                    'timestamp': tick.timestamp
                })

                logger.info(
                    f"🐋 WHALE trade detected: {tick.symbol} - "
                    f"${usd_value:,.0f} ({tick.side.upper()}) @ ${tick.price:,.2f}"
                )

        return large_trades

    async def _get_ticks(
        self,
        symbol: str,
        lookback_seconds: int
    ) -> List[TradeTick]:
        """
        Get trade ticks from database or cache.

        Args:
            symbol: Trading pair
            lookback_seconds: How far back to look

        Returns:
            List of TradeTick objects
        """
        # If DB manager available, query from DuckDB
        if self.db_manager:
            # In production, this would query DuckDB
            # Example SQL: SELECT * FROM ticks WHERE timestamp > NOW() - INTERVAL {lookback_seconds} SECONDS
            pass

        # For now, use in-memory cache
        if symbol in self._tick_cache:
            cutoff_time = datetime.utcnow() - timedelta(seconds=lookback_seconds)
            return [
                tick for tick in self._tick_cache[symbol]
                if tick.timestamp >= cutoff_time
            ]

        return []

    def add_tick(self, tick: TradeTick):
        """
        Add a tick to the cache (for testing without DB).

        Args:
            tick: TradeTick object
        """
        if tick.symbol not in self._tick_cache:
            self._tick_cache[tick.symbol] = []

        self._tick_cache[tick.symbol].append(tick)

        # Keep only last 15 minutes of ticks
        cutoff_time = datetime.utcnow() - timedelta(minutes=15)
        self._tick_cache[tick.symbol] = [
            t for t in self._tick_cache[tick.symbol]
            if t.timestamp >= cutoff_time
        ]

    def clear_cache(self):
        """Clear tick cache."""
        self._tick_cache.clear()


# Example usage and testing
async def test_order_flow_analyzer():
    """Test the order flow analyzer with sample data."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    analyzer = OrderFlowAnalyzer(
        imbalance_threshold=2.5,
        large_trade_threshold_usd=50000
    )

    # Simulate trade ticks
    now = datetime.utcnow()
    symbol = 'BTCUSDT'

    # Add sample ticks - bullish imbalance
    for i in range(100):
        tick = TradeTick(
            symbol=symbol,
            price=95000 + i * 10,
            amount=0.5 if i % 3 == 0 else 0.1,  # Vary amounts
            side='buy' if i < 70 else 'sell',  # 70% buy, 30% sell
            timestamp=now - timedelta(seconds=100 - i),
            exchange='binance'
        )
        analyzer.add_tick(tick)

    # Add a whale trade
    whale_tick = TradeTick(
        symbol=symbol,
        price=95500,
        amount=10.0,  # $955,000 trade
        side='buy',
        timestamp=now - timedelta(seconds=5),
        exchange='binance'
    )
    analyzer.add_tick(whale_tick)

    # Test CVD calculation
    print("\n" + "="*60)
    print("CVD CALCULATION TEST")
    print("="*60)
    cvd_result = await analyzer.calculate_cvd(symbol, lookback_seconds=120)
    print(f"CVD: {cvd_result['cvd']:.2f}")
    print(f"Trend: {cvd_result['trend']}")
    print(f"Buy Volume: {cvd_result['buy_volume']:.2f}")
    print(f"Sell Volume: {cvd_result['sell_volume']:.2f}")

    # Test imbalance detection
    print("\n" + "="*60)
    print("IMBALANCE DETECTION TEST")
    print("="*60)
    imbalance = await analyzer.detect_imbalance(symbol, window_seconds=30)
    print(f"Buy/Sell Ratio: {imbalance['buy_sell_ratio']:.2f}x")
    print(f"Imbalance Detected: {imbalance['imbalance_detected']}")
    print(f"Direction: {imbalance['direction']}")

    # Test large trade detection
    print("\n" + "="*60)
    print("LARGE TRADE DETECTION TEST")
    print("="*60)
    large_trades = await analyzer.detect_large_trades(symbol, lookback_seconds=120)
    print(f"Large trades detected: {len(large_trades)}")
    for trade in large_trades:
        print(f"  ${trade['usd_value']:,.0f} - {trade['side'].upper()}")


if __name__ == "__main__":
    asyncio.run(test_order_flow_analyzer())
