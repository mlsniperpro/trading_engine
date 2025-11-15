"""
Analytics Engine - 24/7 coordinator for all analytics calculations.

Subscribes to TradeTickReceived and CandleCompleted events,
triggers analytics calculations, and emits AnalyticsUpdated events.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AnalyticsSnapshot:
    """Snapshot of all analytics for a symbol at a point in time."""
    symbol: str
    exchange: str
    timestamp: datetime

    # Order flow metrics
    cvd: Optional[float] = None
    cvd_trend: Optional[str] = None  # 'bullish', 'bearish', 'neutral'
    buy_sell_ratio: Optional[float] = None
    imbalance_detected: bool = False
    large_trades_count: int = 0

    # Market profile
    poc: Optional[float] = None  # Point of Control
    vah: Optional[float] = None  # Value Area High
    val: Optional[float] = None  # Value Area Low

    # Microstructure
    rejection_detected: bool = False
    rejection_type: Optional[str] = None  # 'bullish', 'bearish'
    candle_strength: Optional[float] = None

    # Technical indicators
    rsi_1m: Optional[float] = None
    rsi_5m: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    vwap: Optional[float] = None

    # Supply/Demand zones
    nearest_demand_zone: Optional[Dict[str, Any]] = None
    nearest_supply_zone: Optional[Dict[str, Any]] = None

    # Fair Value Gaps
    unfilled_fvgs: list = None

    # Multi-timeframe
    trend_alignment: Optional[str] = None  # 'bullish', 'bearish', 'mixed'

    def __post_init__(self):
        if self.unfilled_fvgs is None:
            self.unfilled_fvgs = []


class AnalyticsEngine:
    """
    Main analytics coordinator - runs 24/7.

    Responsibilities:
    1. Subscribe to TradeTickReceived and CandleCompleted events
    2. Trigger all analytics calculations
    3. Coordinate between different analyzers
    4. Emit AnalyticsUpdated events
    5. Cache latest analytics for fast retrieval
    """

    def __init__(
        self,
        event_bus=None,
        db_manager=None,
        update_interval: float = 2.0  # Update analytics every 2 seconds
    ):
        """
        Initialize Analytics Engine.

        Args:
            event_bus: Event bus for pub/sub (optional for now)
            db_manager: Database manager for DuckDB queries (optional for now)
            update_interval: How often to update analytics (seconds)
        """
        self.event_bus = event_bus
        self.db_manager = db_manager
        self.update_interval = update_interval

        # Cache latest analytics per symbol
        self.analytics_cache: Dict[str, AnalyticsSnapshot] = {}

        # Component analyzers (will be injected)
        self.order_flow_analyzer = None
        self.market_profile_analyzer = None
        self.microstructure_analyzer = None
        self.supply_demand_detector = None
        self.fvg_detector = None
        self.multi_tf_manager = None

        # Runtime state
        self.running = False
        self._task: Optional[asyncio.Task] = None

        # Statistics
        self.total_updates = 0
        self.last_update_time: Optional[datetime] = None

        logger.info("AnalyticsEngine initialized")

    def register_analyzers(
        self,
        order_flow=None,
        market_profile=None,
        microstructure=None,
        supply_demand=None,
        fvg=None,
        multi_tf=None
    ):
        """Register analyzer components (dependency injection)."""
        self.order_flow_analyzer = order_flow
        self.market_profile_analyzer = market_profile
        self.microstructure_analyzer = microstructure
        self.supply_demand_detector = supply_demand
        self.fvg_detector = fvg
        self.multi_tf_manager = multi_tf

        logger.info("Analytics components registered")

    async def start(self):
        """Start the analytics engine (24/7 loop)."""
        if self.running:
            logger.warning("AnalyticsEngine already running")
            return

        self.running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("✅ AnalyticsEngine started - Running 24/7")

    async def stop(self):
        """Stop the analytics engine."""
        if not self.running:
            return

        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("AnalyticsEngine stopped")

    async def _run_loop(self):
        """Main 24/7 analytics loop."""
        while self.running:
            try:
                await self._update_all_analytics()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in analytics loop: {e}", exc_info=True)
                await asyncio.sleep(1)  # Brief pause on error

    async def _update_all_analytics(self):
        """Update analytics for all active symbols."""
        # For now, this is a placeholder
        # In production, this would query active symbols from DB
        # and update analytics for each

        # Example symbols (would come from active trading pairs)
        symbols = ['BTCUSDT', 'ETHUSDT']

        for symbol in symbols:
            try:
                await self.update_analytics(symbol, 'binance')
            except Exception as e:
                logger.error(f"Error updating analytics for {symbol}: {e}")

        self.total_updates += 1
        self.last_update_time = datetime.utcnow()

    async def update_analytics(self, symbol: str, exchange: str) -> AnalyticsSnapshot:
        """
        Update all analytics for a specific symbol.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            exchange: Exchange name (e.g., 'binance')

        Returns:
            AnalyticsSnapshot with all calculated metrics
        """
        snapshot = AnalyticsSnapshot(
            symbol=symbol,
            exchange=exchange,
            timestamp=datetime.utcnow()
        )

        # Order Flow Analytics (if analyzer available)
        if self.order_flow_analyzer:
            try:
                cvd = await self.order_flow_analyzer.calculate_cvd(symbol, lookback_seconds=300)
                imbalance = await self.order_flow_analyzer.detect_imbalance(symbol, window_seconds=30)
                large_trades = await self.order_flow_analyzer.detect_large_trades(symbol)

                snapshot.cvd = cvd.get('cvd')
                snapshot.cvd_trend = cvd.get('trend')
                snapshot.buy_sell_ratio = imbalance.get('buy_sell_ratio')
                snapshot.imbalance_detected = imbalance.get('imbalance_detected', False)
                snapshot.large_trades_count = len(large_trades)
            except Exception as e:
                logger.error(f"Order flow analytics error for {symbol}: {e}")

        # Market Profile Analytics
        if self.market_profile_analyzer:
            try:
                profile = await self.market_profile_analyzer.calculate_profile(symbol, timeframe='15m')
                snapshot.poc = profile.get('poc')
                snapshot.vah = profile.get('vah')
                snapshot.val = profile.get('val')
            except Exception as e:
                logger.error(f"Market profile analytics error for {symbol}: {e}")

        # Microstructure Analytics
        if self.microstructure_analyzer:
            try:
                # Would get latest candle from DB
                rejection = await self.microstructure_analyzer.detect_rejection(symbol)
                snapshot.rejection_detected = rejection.get('detected', False)
                snapshot.rejection_type = rejection.get('type')
                snapshot.candle_strength = rejection.get('strength')
            except Exception as e:
                logger.error(f"Microstructure analytics error for {symbol}: {e}")

        # Supply/Demand Zones
        if self.supply_demand_detector:
            try:
                zones = await self.supply_demand_detector.get_nearest_zones(symbol)
                snapshot.nearest_demand_zone = zones.get('demand')
                snapshot.nearest_supply_zone = zones.get('supply')
            except Exception as e:
                logger.error(f"Supply/demand analytics error for {symbol}: {e}")

        # Fair Value Gaps
        if self.fvg_detector:
            try:
                fvgs = await self.fvg_detector.get_unfilled_fvgs(symbol)
                snapshot.unfilled_fvgs = fvgs
            except Exception as e:
                logger.error(f"FVG analytics error for {symbol}: {e}")

        # Multi-timeframe Analysis
        if self.multi_tf_manager:
            try:
                alignment = await self.multi_tf_manager.check_trend_alignment(symbol)
                snapshot.trend_alignment = alignment.get('alignment')
            except Exception as e:
                logger.error(f"Multi-TF analytics error for {symbol}: {e}")

        # Cache the snapshot
        cache_key = f"{exchange}:{symbol}"
        self.analytics_cache[cache_key] = snapshot

        # Emit event (if event bus available)
        if self.event_bus:
            await self.event_bus.publish('AnalyticsUpdated', {
                'symbol': symbol,
                'exchange': exchange,
                'snapshot': snapshot
            })

        logger.debug(f"Analytics updated for {symbol}")
        return snapshot

    def get_latest_analytics(self, symbol: str, exchange: str) -> Optional[AnalyticsSnapshot]:
        """Get cached analytics for a symbol."""
        cache_key = f"{exchange}:{symbol}"
        return self.analytics_cache.get(cache_key)

    def get_all_analytics(self) -> Dict[str, AnalyticsSnapshot]:
        """Get all cached analytics."""
        return self.analytics_cache.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            'running': self.running,
            'total_updates': self.total_updates,
            'last_update_time': self.last_update_time,
            'cached_symbols': len(self.analytics_cache),
            'update_interval': self.update_interval
        }


# Example usage
async def main():
    """Example of running the analytics engine."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create analytics engine
    engine = AnalyticsEngine(update_interval=2.0)

    # Start engine
    await engine.start()

    try:
        # Run for 30 seconds
        await asyncio.sleep(30)

        # Check statistics
        stats = engine.get_statistics()
        logger.info(f"Engine stats: {stats}")

    finally:
        await engine.stop()


if __name__ == "__main__":
    asyncio.run(main())
