"""
Position data models and state management.

This module defines the Position dataclass and related enums for tracking
trading positions throughout their lifecycle.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any


class PositionState(str, Enum):
    """Position lifecycle states."""
    OPEN = "open"              # Position is active and being monitored
    CLOSING = "closing"        # Position exit order has been placed
    CLOSED = "closed"          # Position is fully closed
    FAILED = "failed"          # Position failed to open or close properly


class PositionSide(str, Enum):
    """Position side (long or short)."""
    LONG = "long"
    SHORT = "short"


class AssetType(str, Enum):
    """Asset classification for risk management."""
    CRYPTO_MAJOR = "crypto_major"          # BTC, ETH
    CRYPTO_REGULAR = "crypto_regular"      # Top 100 coins
    CRYPTO_MEME = "crypto_meme"           # Meme coins (high volatility)
    FOREX = "forex"                        # Forex pairs
    COMMODITIES = "commodities"            # Gold, Oil, etc.


class ExitReason(str, Enum):
    """Reason for position exit."""
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"
    DUMP_DETECTED = "dump_detected"
    MAX_HOLD_TIME = "max_hold_time"
    CIRCUIT_BREAKER = "circuit_breaker"
    PORTFOLIO_HEALTH = "portfolio_health"
    CORRELATION_EXIT = "correlation_exit"
    MANUAL = "manual"
    RECONCILIATION = "reconciliation"


@dataclass
class Position:
    """
    Represents a trading position.

    This dataclass tracks all information about an open or closed position,
    including entry/exit prices, P&L, risk parameters, and state.
    """

    # ========================================================================
    # Identity
    # ========================================================================
    position_id: str
    symbol: str
    exchange: str
    market_type: str  # "spot", "futures", "perp"

    # ========================================================================
    # Position Details
    # ========================================================================
    side: PositionSide
    entry_price: float
    quantity: float
    entry_time: datetime

    # ========================================================================
    # State Management
    # ========================================================================
    state: PositionState = PositionState.OPEN

    # ========================================================================
    # Risk Parameters
    # ========================================================================
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop_distance_pct: float = 0.5  # Default: 0.5% for regular crypto
    asset_type: AssetType = AssetType.CRYPTO_REGULAR

    # ========================================================================
    # Tracking & Monitoring
    # ========================================================================
    current_price: Optional[float] = None
    highest_price: Optional[float] = None  # For long positions
    lowest_price: Optional[float] = None   # For short positions
    trailing_stop_price: Optional[float] = None

    # ========================================================================
    # P&L
    # ========================================================================
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    realized_pnl: Optional[float] = None
    realized_pnl_pct: Optional[float] = None

    # ========================================================================
    # Exit Information
    # ========================================================================
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[ExitReason] = None
    hold_duration_seconds: Optional[float] = None

    # ========================================================================
    # Execution Details
    # ========================================================================
    entry_order_id: Optional[str] = None
    exit_order_id: Optional[str] = None
    commission_paid: float = 0.0
    commission_asset: str = "USDT"

    # ========================================================================
    # Signal Linkage
    # ========================================================================
    signal_id: Optional[str] = None
    strategy_name: Optional[str] = None

    # ========================================================================
    # Metadata
    # ========================================================================
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update_price(self, new_price: float) -> None:
        """
        Update current price and recalculate P&L.

        Args:
            new_price: New market price
        """
        self.current_price = new_price
        self.updated_at = datetime.utcnow()

        # Update highest/lowest prices for trailing stop
        if self.side == PositionSide.LONG:
            if self.highest_price is None or new_price > self.highest_price:
                self.highest_price = new_price
        else:  # SHORT
            if self.lowest_price is None or new_price < self.lowest_price:
                self.lowest_price = new_price

        # Calculate unrealized P&L
        self._calculate_unrealized_pnl()

    def _calculate_unrealized_pnl(self) -> None:
        """Calculate unrealized P&L based on current price."""
        if self.current_price is None:
            return

        if self.side == PositionSide.LONG:
            # Long: profit when price goes up
            price_change = self.current_price - self.entry_price
            self.unrealized_pnl = price_change * self.quantity
            self.unrealized_pnl_pct = (price_change / self.entry_price) * 100
        else:  # SHORT
            # Short: profit when price goes down
            price_change = self.entry_price - self.current_price
            self.unrealized_pnl = price_change * self.quantity
            self.unrealized_pnl_pct = (price_change / self.entry_price) * 100

    def calculate_realized_pnl(self, exit_price: float) -> None:
        """
        Calculate realized P&L on position exit.

        Args:
            exit_price: Price at which position was closed
        """
        if self.side == PositionSide.LONG:
            price_change = exit_price - self.entry_price
            self.realized_pnl = price_change * self.quantity
            self.realized_pnl_pct = (price_change / self.entry_price) * 100
        else:  # SHORT
            price_change = self.entry_price - exit_price
            self.realized_pnl = price_change * self.quantity
            self.realized_pnl_pct = (price_change / self.entry_price) * 100

        # Subtract commission
        self.realized_pnl -= self.commission_paid

    def mark_as_closing(self, exit_order_id: str) -> None:
        """
        Mark position as closing.

        Args:
            exit_order_id: ID of the exit order
        """
        self.state = PositionState.CLOSING
        self.exit_order_id = exit_order_id
        self.updated_at = datetime.utcnow()

    def mark_as_closed(
        self,
        exit_price: float,
        exit_reason: ExitReason,
        commission: float = 0.0
    ) -> None:
        """
        Mark position as closed and calculate final P&L.

        Args:
            exit_price: Price at which position was closed
            exit_reason: Reason for exit
            commission: Commission paid on exit
        """
        self.state = PositionState.CLOSED
        self.exit_price = exit_price
        self.exit_time = datetime.utcnow()
        self.exit_reason = exit_reason
        self.commission_paid += commission
        self.updated_at = datetime.utcnow()

        # Calculate hold duration
        if self.entry_time:
            self.hold_duration_seconds = (
                self.exit_time - self.entry_time
            ).total_seconds()

        # Calculate realized P&L
        self.calculate_realized_pnl(exit_price)

    def update_trailing_stop(self, new_stop_price: float) -> None:
        """
        Update trailing stop price.

        Args:
            new_stop_price: New trailing stop price
        """
        self.trailing_stop_price = new_stop_price
        self.updated_at = datetime.utcnow()

    def is_profitable(self) -> bool:
        """Check if position is currently profitable."""
        return self.unrealized_pnl > 0

    def get_hold_time_minutes(self) -> float:
        """Get hold time in minutes."""
        if self.state == PositionState.CLOSED and self.hold_duration_seconds:
            return self.hold_duration_seconds / 60
        else:
            # Calculate current hold time
            duration = (datetime.utcnow() - self.entry_time).total_seconds()
            return duration / 60

    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary for serialization."""
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "market_type": self.market_type,
            "side": self.side.value,
            "state": self.state.value,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "realized_pnl": self.realized_pnl,
            "realized_pnl_pct": self.realized_pnl_pct,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_reason": self.exit_reason.value if self.exit_reason else None,
            "hold_duration_seconds": self.hold_duration_seconds,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "trailing_stop_price": self.trailing_stop_price,
            "trailing_stop_distance_pct": self.trailing_stop_distance_pct,
            "asset_type": self.asset_type.value,
            "signal_id": self.signal_id,
            "strategy_name": self.strategy_name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Position":
        """
        Create Position from dictionary.

        Args:
            data: Dictionary representation of position

        Returns:
            Position instance
        """
        # Parse enums
        side = PositionSide(data["side"]) if isinstance(data.get("side"), str) else data["side"]
        state = PositionState(data["state"]) if isinstance(data.get("state"), str) else data["state"]
        asset_type = AssetType(data.get("asset_type", "crypto_regular"))
        exit_reason = ExitReason(data["exit_reason"]) if data.get("exit_reason") else None

        # Parse datetimes
        entry_time = datetime.fromisoformat(data["entry_time"]) if isinstance(data.get("entry_time"), str) else data["entry_time"]
        exit_time = datetime.fromisoformat(data["exit_time"]) if data.get("exit_time") and isinstance(data["exit_time"], str) else data.get("exit_time")
        created_at = datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.utcnow())
        updated_at = datetime.fromisoformat(data["updated_at"]) if isinstance(data.get("updated_at"), str) else data.get("updated_at", datetime.utcnow())

        return cls(
            position_id=data["position_id"],
            symbol=data["symbol"],
            exchange=data["exchange"],
            market_type=data["market_type"],
            side=side,
            state=state,
            entry_price=data["entry_price"],
            exit_price=data.get("exit_price"),
            quantity=data["quantity"],
            current_price=data.get("current_price"),
            unrealized_pnl=data.get("unrealized_pnl", 0.0),
            unrealized_pnl_pct=data.get("unrealized_pnl_pct", 0.0),
            realized_pnl=data.get("realized_pnl"),
            realized_pnl_pct=data.get("realized_pnl_pct"),
            entry_time=entry_time,
            exit_time=exit_time,
            exit_reason=exit_reason,
            hold_duration_seconds=data.get("hold_duration_seconds"),
            stop_loss=data.get("stop_loss"),
            take_profit=data.get("take_profit"),
            trailing_stop_price=data.get("trailing_stop_price"),
            trailing_stop_distance_pct=data.get("trailing_stop_distance_pct", 0.5),
            highest_price=data.get("highest_price"),
            lowest_price=data.get("lowest_price"),
            asset_type=asset_type,
            entry_order_id=data.get("entry_order_id"),
            exit_order_id=data.get("exit_order_id"),
            commission_paid=data.get("commission_paid", 0.0),
            commission_asset=data.get("commission_asset", "USDT"),
            signal_id=data.get("signal_id"),
            strategy_name=data.get("strategy_name"),
            created_at=created_at,
            updated_at=updated_at,
            metadata=data.get("metadata", {}),
        )
