"""
Position Reconciliation Service.

Reconciles local position state with exchange state on startup.
Handles discrepancies and ensures system consistency after crashes or restarts.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from position.models import Position, PositionSide, PositionState, AssetType, ExitReason


logger = logging.getLogger(__name__)


@dataclass
class PositionDiscrepancy:
    """Represents a discrepancy between local and exchange positions."""
    position_id: str
    symbol: str
    discrepancy_type: str  # "missing_local", "missing_exchange", "state_mismatch", "quantity_mismatch"
    local_state: Optional[Dict]
    exchange_state: Optional[Dict]
    resolution: str  # How the discrepancy was resolved


class PositionReconciler:
    """
    Position reconciliation service.

    Compares local position state (from database) with exchange state
    and resolves any discrepancies.

    Reconciliation Strategy:
    1. Exchange is source of truth for OPEN positions
    2. If position missing locally but exists on exchange → add to local
    3. If position exists locally but missing on exchange → mark as closed
    4. If quantity/price mismatch → update local to match exchange
    """

    def __init__(self, config: Dict):
        """
        Initialize position reconciler.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.PositionReconciler")
        self.discrepancies: List[PositionDiscrepancy] = []

    async def reconcile(self, position_monitor) -> Dict:
        """
        Reconcile positions with exchange.

        Args:
            position_monitor: PositionMonitor instance

        Returns:
            Reconciliation summary
        """
        self.logger.info("=" * 70)
        self.logger.info("Starting Position Reconciliation")
        self.logger.info("=" * 70)

        # Step 1: Get local positions (from database or in-memory)
        local_positions = await self._get_local_positions(position_monitor)
        self.logger.info(f"  • Local positions: {len(local_positions)}")

        # Step 2: Get exchange positions (from exchange API)
        exchange_positions = await self._get_exchange_positions()
        self.logger.info(f"  • Exchange positions: {len(exchange_positions)}")

        # Step 3: Find discrepancies
        discrepancies = await self._find_discrepancies(
            local_positions,
            exchange_positions
        )
        self.logger.info(f"  • Discrepancies found: {len(discrepancies)}")

        # Step 4: Resolve discrepancies
        if discrepancies:
            await self._resolve_discrepancies(
                discrepancies,
                position_monitor
            )

        # Step 5: Generate summary
        summary = self._generate_summary(
            local_positions,
            exchange_positions,
            discrepancies
        )

        self.logger.info("=" * 70)
        self.logger.info("Position Reconciliation Complete")
        self.logger.info(f"  • Reconciled: {summary['positions_reconciled']}")
        self.logger.info(f"  • Added: {summary['positions_added']}")
        self.logger.info(f"  • Closed: {summary['positions_closed']}")
        self.logger.info(f"  • Updated: {summary['positions_updated']}")
        self.logger.info("=" * 70)

        return summary

    async def _get_local_positions(
        self,
        position_monitor
    ) -> Dict[str, Position]:
        """
        Get local positions from position monitor.

        In production, this would also check a database (Firestore, PostgreSQL, etc.)
        to recover positions from before the system restarted.

        Args:
            position_monitor: PositionMonitor instance

        Returns:
            Dict of position_id -> Position
        """
        # Get from position monitor
        local_positions = position_monitor.get_all_positions()

        # TODO: In production, also load from database:
        # - Query Firestore/PostgreSQL for positions with state=OPEN
        # - Merge with in-memory positions
        # - Return combined set

        return local_positions

    async def _get_exchange_positions(self) -> Dict[str, Dict]:
        """
        Get open positions from exchange.

        In production, this would query the exchange API (CCXT or direct API)
        to get all currently open positions.

        Returns:
            Dict of position_key -> exchange_position_data
        """
        # TODO: In production, query exchange(s):
        # - For spot: Check open orders + filled orders without corresponding sells
        # - For futures/perp: Use positions endpoint
        # - Return normalized position data

        # Mock implementation (returns empty for now)
        exchange_positions = {}

        # Example of what exchange data might look like:
        # exchange_positions = {
        #     "binance:ETHUSDT:long": {
        #         "symbol": "ETHUSDT",
        #         "side": "long",
        #         "entry_price": 3000.0,
        #         "quantity": 1.0,
        #         "current_price": 3010.0,
        #         "unrealized_pnl": 10.0,
        #     }
        # }

        return exchange_positions

    async def _find_discrepancies(
        self,
        local_positions: Dict[str, Position],
        exchange_positions: Dict[str, Dict]
    ) -> List[PositionDiscrepancy]:
        """
        Find discrepancies between local and exchange positions.

        Args:
            local_positions: Local positions
            exchange_positions: Exchange positions

        Returns:
            List of discrepancies
        """
        discrepancies = []

        # Create lookup keys for local positions
        local_keys = {
            self._create_position_key(pos): (pos.position_id, pos)
            for pos in local_positions.values()
            if pos.state == PositionState.OPEN
        }

        # Check for positions on exchange but not in local state
        for exchange_key, exchange_data in exchange_positions.items():
            if exchange_key not in local_keys:
                discrepancies.append(
                    PositionDiscrepancy(
                        position_id="",
                        symbol=exchange_data['symbol'],
                        discrepancy_type="missing_local",
                        local_state=None,
                        exchange_state=exchange_data,
                        resolution="pending"
                    )
                )
                self.logger.warning(
                    f"  ⚠ Missing locally: {exchange_data['symbol']} "
                    f"{exchange_data['side']} @ {exchange_data['entry_price']}"
                )

        # Check for positions in local state but not on exchange
        for local_key, (position_id, position) in local_keys.items():
            if local_key not in exchange_positions:
                discrepancies.append(
                    PositionDiscrepancy(
                        position_id=position_id,
                        symbol=position.symbol,
                        discrepancy_type="missing_exchange",
                        local_state=position.to_dict(),
                        exchange_state=None,
                        resolution="pending"
                    )
                )
                self.logger.warning(
                    f"  ⚠ Missing on exchange: {position.symbol} "
                    f"{position.side.value} @ {position.entry_price}"
                )
            else:
                # Position exists in both - check for state mismatches
                exchange_data = exchange_positions[local_key]
                mismatch = self._check_state_mismatch(position, exchange_data)

                if mismatch:
                    discrepancies.append(
                        PositionDiscrepancy(
                            position_id=position_id,
                            symbol=position.symbol,
                            discrepancy_type=mismatch,
                            local_state=position.to_dict(),
                            exchange_state=exchange_data,
                            resolution="pending"
                        )
                    )
                    self.logger.warning(
                        f"  ⚠ State mismatch: {position.symbol} - {mismatch}"
                    )

        return discrepancies

    def _create_position_key(self, position: Position) -> str:
        """
        Create a unique key for a position.

        Args:
            position: Position object

        Returns:
            Unique key string
        """
        return f"{position.exchange}:{position.symbol}:{position.side.value}"

    def _check_state_mismatch(
        self,
        local_position: Position,
        exchange_data: Dict
    ) -> Optional[str]:
        """
        Check for state mismatches between local and exchange.

        Args:
            local_position: Local position
            exchange_data: Exchange position data

        Returns:
            Mismatch type or None
        """
        # Check quantity mismatch (>1% difference)
        local_qty = local_position.quantity
        exchange_qty = exchange_data.get('quantity', 0)

        if abs(local_qty - exchange_qty) / local_qty > 0.01:
            return "quantity_mismatch"

        # Check price mismatch (>1% difference)
        local_price = local_position.entry_price
        exchange_price = exchange_data.get('entry_price', 0)

        if abs(local_price - exchange_price) / local_price > 0.01:
            return "price_mismatch"

        return None

    async def _resolve_discrepancies(
        self,
        discrepancies: List[PositionDiscrepancy],
        position_monitor
    ):
        """
        Resolve discrepancies.

        Args:
            discrepancies: List of discrepancies
            position_monitor: PositionMonitor instance
        """
        for discrepancy in discrepancies:
            if discrepancy.discrepancy_type == "missing_local":
                # Position exists on exchange but not locally → add it
                await self._add_missing_position(
                    discrepancy.exchange_state,
                    position_monitor
                )
                discrepancy.resolution = "added_to_local"

            elif discrepancy.discrepancy_type == "missing_exchange":
                # Position exists locally but not on exchange → mark as closed
                await self._close_missing_position(
                    discrepancy.position_id,
                    position_monitor
                )
                discrepancy.resolution = "marked_closed"

            elif discrepancy.discrepancy_type in ["quantity_mismatch", "price_mismatch"]:
                # Update local state to match exchange (exchange is source of truth)
                await self._update_position_state(
                    discrepancy.position_id,
                    discrepancy.exchange_state,
                    position_monitor
                )
                discrepancy.resolution = "updated_from_exchange"

        self.discrepancies = discrepancies

    async def _add_missing_position(
        self,
        exchange_data: Dict,
        position_monitor
    ):
        """
        Add a position that exists on exchange but not locally.

        Args:
            exchange_data: Exchange position data
            position_monitor: PositionMonitor instance
        """
        self.logger.info(
            f"  ✓ Adding missing position: {exchange_data['symbol']} "
            f"{exchange_data['side']}"
        )

        # Create Position object from exchange data
        position = self._create_position_from_exchange(exchange_data)

        # Add to trailing stop manager
        await position_monitor.trailing_stop_manager.add_position(position)

        # Add to position monitor
        position_monitor.positions[position.position_id] = position

    async def _close_missing_position(
        self,
        position_id: str,
        position_monitor
    ):
        """
        Close a position that exists locally but not on exchange.

        Args:
            position_id: Position ID
            position_monitor: PositionMonitor instance
        """
        position = position_monitor.get_position(position_id)
        if not position:
            return

        self.logger.info(
            f"  ✓ Closing missing position: {position.symbol} "
            f"{position.side.value}"
        )

        # Mark as closed with reconciliation reason
        position.mark_as_closed(
            exit_price=position.current_price or position.entry_price,
            exit_reason=ExitReason.RECONCILIATION,
            commission=0.0
        )

        # Remove from trailing stop manager
        await position_monitor.trailing_stop_manager.remove_position(position_id)

    async def _update_position_state(
        self,
        position_id: str,
        exchange_data: Dict,
        position_monitor
    ):
        """
        Update local position state to match exchange.

        Args:
            position_id: Position ID
            exchange_data: Exchange position data
            position_monitor: PositionMonitor instance
        """
        position = position_monitor.get_position(position_id)
        if not position:
            return

        self.logger.info(
            f"  ✓ Updating position state: {position.symbol}"
        )

        # Update from exchange data
        if 'quantity' in exchange_data:
            position.quantity = exchange_data['quantity']

        if 'entry_price' in exchange_data:
            position.entry_price = exchange_data['entry_price']

        if 'current_price' in exchange_data:
            position.update_price(exchange_data['current_price'])

    def _create_position_from_exchange(self, exchange_data: Dict) -> Position:
        """
        Create a Position object from exchange data.

        Args:
            exchange_data: Exchange position data

        Returns:
            Position object
        """
        import uuid

        position_id = str(uuid.uuid4())

        return Position(
            position_id=position_id,
            symbol=exchange_data['symbol'],
            exchange=exchange_data.get('exchange', 'binance'),
            market_type=exchange_data.get('market_type', 'spot'),
            side=PositionSide(exchange_data['side']),
            entry_price=exchange_data['entry_price'],
            quantity=exchange_data['quantity'],
            entry_time=datetime.utcnow(),  # Approximate
            state=PositionState.OPEN,
            current_price=exchange_data.get('current_price'),
            unrealized_pnl=exchange_data.get('unrealized_pnl', 0.0),
            asset_type=AssetType.CRYPTO_REGULAR,  # Default
        )

    def _generate_summary(
        self,
        local_positions: Dict[str, Position],
        exchange_positions: Dict[str, Dict],
        discrepancies: List[PositionDiscrepancy]
    ) -> Dict:
        """
        Generate reconciliation summary.

        Args:
            local_positions: Local positions
            exchange_positions: Exchange positions
            discrepancies: List of discrepancies

        Returns:
            Summary dictionary
        """
        positions_added = sum(
            1 for d in discrepancies
            if d.discrepancy_type == "missing_local"
        )

        positions_closed = sum(
            1 for d in discrepancies
            if d.discrepancy_type == "missing_exchange"
        )

        positions_updated = sum(
            1 for d in discrepancies
            if d.discrepancy_type in ["quantity_mismatch", "price_mismatch"]
        )

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "local_positions_count": len(local_positions),
            "exchange_positions_count": len(exchange_positions),
            "discrepancies_found": len(discrepancies),
            "positions_reconciled": len(discrepancies),
            "positions_added": positions_added,
            "positions_closed": positions_closed,
            "positions_updated": positions_updated,
            "discrepancies": [
                {
                    "position_id": d.position_id,
                    "symbol": d.symbol,
                    "type": d.discrepancy_type,
                    "resolution": d.resolution,
                }
                for d in discrepancies
            ],
        }


# ============================================================================
# Testing
# ============================================================================

async def test_reconciliation():
    """Test position reconciliation."""
    logger = logging.getLogger("test_reconciliation")

    # Create mock position monitor
    from position.monitor import PositionMonitor

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

    # Create reconciler
    reconciler = PositionReconciler(config)

    # Run reconciliation
    summary = await reconciler.reconcile(monitor)

    logger.info(f"Reconciliation summary: {summary}")

    await monitor.stop()


if __name__ == "__main__":
    # Run test
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(test_reconciliation())
