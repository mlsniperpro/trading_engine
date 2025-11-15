"""
Position Monitor - Always-on position monitoring system.

Subscribes to PositionOpened events and monitors positions 24/7.
Emits PositionClosed events when positions are closed.
"""

import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime
import uuid

from position.models import Position, PositionSide, AssetType, PositionState, ExitReason
from position.trailing_stop import TrailingStopManager
from position.portfolio_risk_manager import PortfolioRiskManager
from core.simple_events import (
    event_bus,
    PositionOpened,
    PositionClosed,
    OrderSide,
)


logger = logging.getLogger(__name__)


class PositionMonitor:
    """
    Always-on position monitoring system.

    Features:
    - Subscribes to PositionOpened events
    - Tracks all open positions
    - Monitors P&L continuously
    - Integrates with TrailingStopManager
    - Integrates with PortfolioRiskManager
    - Emits PositionClosed events
    """

    def __init__(self, config: Dict):
        """
        Initialize position monitor.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.PositionMonitor")

        # Components
        self.trailing_stop_manager = TrailingStopManager()
        self.portfolio_risk_manager = PortfolioRiskManager(
            config.get('portfolio_risk', {})
        )

        # State
        self.positions: Dict[str, Position] = {}  # position_id -> Position
        self.is_running = False
        self.monitoring_task = None

    async def start(self):
        """Start the position monitor."""
        self.is_running = True

        # Subscribe to events
        await event_bus.subscribe("PositionOpened", self.on_position_opened)

        # Start portfolio risk manager
        await self.portfolio_risk_manager.start(self.trailing_stop_manager)

        # Start monitoring loop
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())

        self.logger.info("=" * 70)
        self.logger.info("Position Monitor started (24/7 monitoring)")
        self.logger.info("  • Trailing stops enabled")
        self.logger.info("  • Portfolio risk management enabled")
        self.logger.info("  • Subscribed to PositionOpened events")
        self.logger.info("=" * 70)

    async def stop(self):
        """Stop the position monitor."""
        self.is_running = False

        # Stop portfolio risk manager
        await self.portfolio_risk_manager.stop()

        # Cancel monitoring task
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Position Monitor stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop for periodic tasks."""
        while self.is_running:
            try:
                # Log stats every minute
                await self._log_stats()
                await asyncio.sleep(60)
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)

    async def _log_stats(self):
        """Log position monitoring statistics."""
        stats = self.get_stats()

        if stats['open_positions'] > 0:
            self.logger.info(
                f"[MONITOR] Positions: {stats['open_positions']} open | "
                f"Profitable: {stats['profitable_positions']} | "
                f"Total P&L: {stats['total_unrealized_pnl']:+.2f} USDT"
            )

    async def on_position_opened(self, event: PositionOpened):
        """
        Handle PositionOpened event.

        Args:
            event: PositionOpened event
        """
        self.logger.info(
            f"[MONITOR] 📈 Position Opened: {event.symbol} {event.side.value} | "
            f"Entry: {event.entry_price:.8f} | "
            f"Qty: {event.quantity} | "
            f"Trailing: {event.trailing_stop_distance_pct}%"
        )

        # Create Position object
        position = Position(
            position_id=event.position_id,
            symbol=event.symbol,
            exchange=event.exchange,
            market_type=event.market_type,
            side=PositionSide(event.side.value),
            entry_price=event.entry_price,
            quantity=event.quantity,
            entry_time=event.timestamp,
            state=PositionState.OPEN,
            stop_loss=event.stop_loss,
            take_profit=event.take_profit,
            trailing_stop_distance_pct=event.trailing_stop_distance_pct,
            signal_id=event.signal_id,
            entry_order_id=event.order_id,
            asset_type=self._detect_asset_type(event.symbol, event.market_type),
        )

        # Add to tracking
        self.positions[position.position_id] = position

        # Add to trailing stop manager
        await self.trailing_stop_manager.add_position(position)

        self.logger.info(
            f"[MONITOR] Position {event.position_id} added to monitoring"
        )


    def _detect_asset_type(self, symbol: str, market_type: str) -> AssetType:
        """
        Detect asset type from symbol.

        Args:
            symbol: Trading symbol
            market_type: Market type (spot, futures, etc.)

        Returns:
            AssetType
        """
        symbol_upper = symbol.upper()

        # Major crypto
        if any(major in symbol_upper for major in ['BTC', 'ETH']):
            return AssetType.CRYPTO_MAJOR

        # Meme coins
        meme_keywords = ['DOGE', 'SHIB', 'PEPE', 'BONK', 'WIF', 'MEME', 'FLOKI']
        if any(meme in symbol_upper for meme in meme_keywords):
            return AssetType.CRYPTO_MEME

        # Forex
        forex_pairs = ['EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'NZD']
        if any(pair in symbol_upper for pair in forex_pairs):
            return AssetType.FOREX

        # Default: regular crypto
        return AssetType.CRYPTO_REGULAR

    async def update_price(self, symbol: str, price: float):
        """
        Update price for a symbol.

        This triggers trailing stop updates and portfolio risk checks.

        Args:
            symbol: Symbol
            price: Current market price
        """
        # Update trailing stops
        await self.trailing_stop_manager.update_on_tick(symbol, price)

        # Update correlation monitor (for BTC/ETH)
        await self.portfolio_risk_manager.correlation_monitor.update_price(
            symbol,
            price
        )

    async def force_close_position(
        self,
        position_id: str,
        exit_price: float,
        exit_reason: ExitReason,
        reason_text: str
    ):
        """
        Force close a position.

        Args:
            position_id: Position ID
            exit_price: Exit price
            exit_reason: Exit reason enum
            reason_text: Human-readable reason
        """
        position = self.positions.get(position_id)
        if not position:
            self.logger.warning(f"Position {position_id} not found")
            return

        # Use trailing stop manager to close
        await self.trailing_stop_manager.manual_exit(
            position_id,
            exit_price,
            reason_text
        )

        self.logger.info(
            f"[MONITOR] Force closed {position.symbol} | "
            f"Reason: {reason_text}"
        )

    def get_position(self, position_id: str) -> Optional[Position]:
        """
        Get position by ID.

        Args:
            position_id: Position ID

        Returns:
            Position or None
        """
        return self.positions.get(position_id)

    def get_all_positions(self) -> Dict[str, Position]:
        """
        Get all tracked positions.

        Returns:
            Dict of position_id -> Position
        """
        return self.positions.copy()

    def get_open_positions(self) -> Dict[str, Position]:
        """
        Get all open positions.

        Returns:
            Dict of position_id -> Position (only open positions)
        """
        return {
            pid: pos for pid, pos in self.positions.items()
            if pos.state == PositionState.OPEN
        }

    def get_stats(self) -> Dict:
        """
        Get position monitoring statistics.

        Returns:
            Statistics dictionary
        """
        open_positions = self.get_open_positions()

        total_unrealized_pnl = sum(
            pos.unrealized_pnl for pos in open_positions.values()
        )
        profitable_count = sum(
            1 for pos in open_positions.values() if pos.is_profitable()
        )

        return {
            "total_positions": len(self.positions),
            "open_positions": len(open_positions),
            "profitable_positions": profitable_count,
            "losing_positions": len(open_positions) - profitable_count,
            "total_unrealized_pnl": total_unrealized_pnl,
            "symbols": list(set(pos.symbol for pos in open_positions.values())),
        }

    async def reconcile_positions(self):
        """
        Reconcile positions with exchange on startup.

        This is called on system startup to ensure local state
        matches exchange state.
        """
        from position.reconciliation import PositionReconciler

        reconciler = PositionReconciler(self.config)
        await reconciler.reconcile(self)

        self.logger.info("[MONITOR] Position reconciliation complete")


# ============================================================================
# Convenience Functions
# ============================================================================

def create_mock_position(
    symbol: str = "ETHUSDT",
    side: PositionSide = PositionSide.LONG,
    entry_price: float = 3000.0,
    quantity: float = 1.0,
    asset_type: AssetType = AssetType.CRYPTO_REGULAR
) -> Position:
    """
    Create a mock position for testing.

    Args:
        symbol: Trading symbol
        side: Position side
        entry_price: Entry price
        quantity: Position size
        asset_type: Asset type

    Returns:
        Mock Position object
    """
    position_id = str(uuid.uuid4())

    return Position(
        position_id=position_id,
        symbol=symbol,
        exchange="binance",
        market_type="spot",
        side=side,
        entry_price=entry_price,
        quantity=quantity,
        entry_time=datetime.utcnow(),
        state=PositionState.OPEN,
        asset_type=asset_type,
        trailing_stop_distance_pct=0.5 if asset_type != AssetType.CRYPTO_MEME else 17.5,
    )


async def test_position_monitoring():
    """Test position monitoring with mock data."""
    logger = logging.getLogger("test_position_monitoring")

    # Create position monitor
    config = {
        'portfolio_risk': {
            'dump_detection': {},
            'correlation': {},
            'health': {},
            'circuit_breaker': {},
            'hold_time': {},
        }
    }

    monitor = PositionMonitor(config)
    await monitor.start()

    # Create mock position
    position = create_mock_position(
        symbol="ETHUSDT",
        side=PositionSide.LONG,
        entry_price=3000.0,
        quantity=1.0,
        asset_type=AssetType.CRYPTO_REGULAR
    )

    # Simulate PositionOpened event
    event = PositionOpened(
        position_id=position.position_id,
        symbol=position.symbol,
        side=position.side,
        entry_price=position.entry_price,
        quantity=position.quantity,
        exchange=position.exchange,
        market_type=position.market_type,
        trailing_stop_distance_pct=position.trailing_stop_distance_pct,
        timestamp=datetime.utcnow(),
        metadata={}
    )

    await monitor.on_position_opened(event)

    logger.info(f"Created mock position: {position.position_id}")

    # Simulate price updates
    prices = [3010, 3020, 3030, 3025, 3020, 3015, 3010, 3005]

    for price in prices:
        await monitor.update_price("ETHUSDT", price)
        logger.info(f"Price: {price} | P&L: {position.unrealized_pnl_pct:+.2f}%")
        await asyncio.sleep(1)

    # Get stats
    stats = monitor.get_stats()
    logger.info(f"Stats: {stats}")

    await monitor.stop()


if __name__ == "__main__":
    # Run test
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(test_position_monitoring())
