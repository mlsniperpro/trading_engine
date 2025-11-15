"""
Trailing Stop Manager for position risk management.

Manages trailing stops for all open positions with:
- Dynamic trailing distances based on asset type
- Regular crypto: 0.5% trailing distance
- Meme coins: 15-20% trailing distance (avg 17.5%)
- Thread-safe updates on every price tick
"""

import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime

from position.models import Position, PositionSide, AssetType, ExitReason, PositionState
from core.simple_events import event_bus, PositionClosed, OrderSide


logger = logging.getLogger(__name__)


class TrailingStopManager:
    """
    Manages trailing stop-losses for all open positions.

    The trailing stop automatically adjusts as the price moves in favor
    of the position, locking in profits while allowing the position to run.

    Features:
    - Asset-specific trailing distances
    - Thread-safe per-position updates
    - Activates immediately on position entry
    - Emits PositionClosed events when stop is hit
    """

    # Trailing distance percentages
    TRAILING_DISTANCE_REGULAR = 0.5      # 0.5% for regular crypto/forex
    TRAILING_DISTANCE_MEME = 17.5        # 17.5% for meme coins (avg of 15-20%)
    TRAILING_DISTANCE_MAJOR = 0.3        # 0.3% for BTC/ETH (tighter)

    def __init__(self):
        """Initialize the trailing stop manager."""
        self.positions: Dict[str, Position] = {}
        self.position_locks: Dict[str, asyncio.Lock] = {}
        self.logger = logging.getLogger(f"{__name__}.TrailingStopManager")

    async def add_position(self, position: Position) -> None:
        """
        Add position to trailing stop tracking.

        Activates trailing stop immediately on entry.

        Args:
            position: Position object to track
        """
        position_id = position.position_id

        # Create lock for this position
        self.position_locks[position_id] = asyncio.Lock()

        # Determine trailing distance based on asset type
        trailing_pct = self._get_trailing_distance(position.asset_type, position.symbol)
        position.trailing_stop_distance_pct = trailing_pct

        # Calculate initial trailing stop price
        initial_stop = self._calculate_initial_stop(position, trailing_pct)
        position.update_trailing_stop(initial_stop)

        # Initialize highest/lowest price tracking
        if position.side == PositionSide.LONG:
            position.highest_price = position.entry_price
        else:
            position.lowest_price = position.entry_price

        # Store position
        self.positions[position_id] = position

        self.logger.info(
            f"[TSL] Added {position.symbol} {position.side.value} | "
            f"Entry: {position.entry_price:.8f} | "
            f"Initial Stop: {initial_stop:.8f} ({trailing_pct}% trailing)"
        )

    def _get_trailing_distance(self, asset_type: AssetType, symbol: str) -> float:
        """
        Get appropriate trailing distance based on asset type.

        Args:
            asset_type: Type of asset
            symbol: Symbol (used for meme coin detection)

        Returns:
            Trailing distance percentage
        """
        # Major crypto (BTC, ETH) - tighter stops
        if asset_type == AssetType.CRYPTO_MAJOR:
            return self.TRAILING_DISTANCE_MAJOR

        # Meme coins - wider stops to handle volatility
        if asset_type == AssetType.CRYPTO_MEME:
            return self.TRAILING_DISTANCE_MEME

        # Check symbol for meme coin indicators (fallback)
        meme_keywords = ['DOGE', 'SHIB', 'PEPE', 'BONK', 'WIF', 'MEME']
        if any(keyword in symbol.upper() for keyword in meme_keywords):
            return self.TRAILING_DISTANCE_MEME

        # Regular crypto/forex - standard trailing
        return self.TRAILING_DISTANCE_REGULAR

    def _calculate_initial_stop(self, position: Position, trailing_pct: float) -> float:
        """
        Calculate initial trailing stop price.

        Args:
            position: Position object
            trailing_pct: Trailing distance percentage

        Returns:
            Initial stop price
        """
        entry = position.entry_price
        distance = entry * (trailing_pct / 100)

        if position.side == PositionSide.LONG:
            # Long: stop below entry
            return entry - distance
        else:
            # Short: stop above entry
            return entry + distance

    async def update_on_tick(self, symbol: str, current_price: float) -> None:
        """
        Update trailing stops for all positions of this symbol.

        Called on EVERY tick update. Thread-safe with per-position locks
        to prevent race conditions.

        Args:
            symbol: Symbol that received price update
            current_price: New market price
        """
        # Get all position IDs for this symbol (read-only, no lock needed)
        position_ids = [
            pid for pid, pos in self.positions.items()
            if pos.symbol == symbol and pos.state == PositionState.OPEN
        ]

        if not position_ids:
            return

        # Update each position (thread-safe with per-position locks)
        for position_id in position_ids:
            async with self.position_locks[position_id]:
                pos = self.positions.get(position_id)
                if not pos or pos.state != PositionState.OPEN:
                    continue

                # Update current price
                pos.update_price(current_price)

                trailing_pct = pos.trailing_stop_distance_pct

                # LONG POSITION LOGIC
                if pos.side == PositionSide.LONG:
                    # Trail stop UP if price makes new high
                    if current_price > pos.highest_price:
                        pos.highest_price = current_price
                        distance = current_price * (trailing_pct / 100)
                        new_stop = current_price - distance

                        # Only move stop UP, never down
                        if new_stop > pos.trailing_stop_price:
                            pos.update_trailing_stop(new_stop)
                            self.logger.debug(
                                f"[TSL] {symbol} Long stop trailed UP to {new_stop:.8f} "
                                f"(price: {current_price:.8f})"
                            )

                    # Check if stop hit
                    if current_price <= pos.trailing_stop_price:
                        await self._trigger_stop(position_id, current_price, "Trailing stop hit")

                # SHORT POSITION LOGIC
                elif pos.side == PositionSide.SHORT:
                    # Trail stop DOWN if price makes new low
                    if current_price < pos.lowest_price:
                        pos.lowest_price = current_price
                        distance = current_price * (trailing_pct / 100)
                        new_stop = current_price + distance

                        # Only move stop DOWN, never up
                        if new_stop < pos.trailing_stop_price:
                            pos.update_trailing_stop(new_stop)
                            self.logger.debug(
                                f"[TSL] {symbol} Short stop trailed DOWN to {new_stop:.8f} "
                                f"(price: {current_price:.8f})"
                            )

                    # Check if stop hit
                    if current_price >= pos.trailing_stop_price:
                        await self._trigger_stop(position_id, current_price, "Trailing stop hit")

    async def _trigger_stop(
        self,
        position_id: str,
        exit_price: float,
        reason: str
    ) -> None:
        """
        Trigger trailing stop loss.

        Args:
            position_id: Position ID
            exit_price: Price at which stop was triggered
            reason: Reason for stop trigger
        """
        pos = self.positions.get(position_id)
        if not pos:
            return

        # Mark position as closing
        pos.mark_as_closing(f"trailing_stop_{position_id}")

        # Calculate P&L
        pos.mark_as_closed(
            exit_price=exit_price,
            exit_reason=ExitReason.TRAILING_STOP,
            commission=0.0  # Will be updated by execution handler
        )

        self.logger.warning(
            f"[TSL] 🛑 STOP TRIGGERED: {pos.symbol} {pos.side.value} | "
            f"Entry: {pos.entry_price:.8f} | Exit: {exit_price:.8f} | "
            f"P&L: {pos.realized_pnl_pct:+.2f}% ({pos.realized_pnl:+.2f} USDT) | "
            f"Hold: {pos.get_hold_time_minutes():.1f}m"
        )

        # Emit PositionClosed event
        event = PositionClosed(
            position_id=pos.position_id,
            symbol=pos.symbol,
            side=OrderSide(pos.side.value),
            entry_price=pos.entry_price,
            exit_price=exit_price,
            quantity=pos.quantity,
            exchange=pos.exchange,
            realized_pnl=pos.realized_pnl,
            realized_pnl_pct=pos.realized_pnl_pct,
            exit_reason=ExitReason.TRAILING_STOP.value,
            hold_duration_seconds=pos.hold_duration_seconds,
            timestamp=datetime.utcnow(),
            metadata={
                "trailing_stop_price": pos.trailing_stop_price,
                "trailing_distance_pct": pos.trailing_stop_distance_pct,
                "highest_price": pos.highest_price,
                "lowest_price": pos.lowest_price,
            }
        )

        await event_bus.publish(event)

        # Remove from tracking
        await self.remove_position(position_id)

    async def remove_position(self, position_id: str) -> None:
        """
        Remove position from tracking.

        Args:
            position_id: Position ID to remove
        """
        if position_id in self.positions:
            pos = self.positions[position_id]
            del self.positions[position_id]
            del self.position_locks[position_id]

            self.logger.info(
                f"[TSL] Removed {pos.symbol} from trailing stop tracking"
            )

    async def manual_exit(
        self,
        position_id: str,
        exit_price: float,
        reason: str = "Manual exit"
    ) -> None:
        """
        Manually exit a position (called by other risk managers).

        Args:
            position_id: Position ID
            exit_price: Exit price
            reason: Exit reason
        """
        async with self.position_locks.get(position_id, asyncio.Lock()):
            pos = self.positions.get(position_id)
            if not pos or pos.state != PositionState.OPEN:
                return

            # Mark as closed
            pos.mark_as_closed(
                exit_price=exit_price,
                exit_reason=ExitReason.MANUAL,
                commission=0.0
            )

            self.logger.info(
                f"[TSL] Manual exit: {pos.symbol} | "
                f"P&L: {pos.realized_pnl_pct:+.2f}% | "
                f"Reason: {reason}"
            )

            # Remove from tracking
            await self.remove_position(position_id)

    def get_position(self, position_id: str) -> Optional[Position]:
        """
        Get position by ID.

        Args:
            position_id: Position ID

        Returns:
            Position object or None
        """
        return self.positions.get(position_id)

    def get_all_positions(self) -> Dict[str, Position]:
        """
        Get all tracked positions.

        Returns:
            Dictionary of position_id -> Position
        """
        return self.positions.copy()

    def get_positions_for_symbol(self, symbol: str) -> Dict[str, Position]:
        """
        Get all positions for a specific symbol.

        Args:
            symbol: Symbol to filter by

        Returns:
            Dictionary of position_id -> Position
        """
        return {
            pid: pos for pid, pos in self.positions.items()
            if pos.symbol == symbol
        }

    def get_stats(self) -> Dict[str, any]:
        """
        Get statistics about tracked positions.

        Returns:
            Statistics dictionary
        """
        open_positions = [p for p in self.positions.values() if p.state == PositionState.OPEN]

        total_unrealized_pnl = sum(p.unrealized_pnl for p in open_positions)
        profitable_count = sum(1 for p in open_positions if p.is_profitable())

        return {
            "total_positions": len(self.positions),
            "open_positions": len(open_positions),
            "profitable_positions": profitable_count,
            "losing_positions": len(open_positions) - profitable_count,
            "total_unrealized_pnl": total_unrealized_pnl,
            "symbols": list(set(p.symbol for p in open_positions)),
        }
