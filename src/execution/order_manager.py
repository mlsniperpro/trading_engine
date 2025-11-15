"""
Order manager for tracking order lifecycle and state.

Manages pending orders, order updates, and order history.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from src.core.events import OrderSide, OrderType, OrderStatus

logger = logging.getLogger(__name__)


class OrderState(str, Enum):
    """Order lifecycle state."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACTIVE = "active"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass
class ManagedOrder:
    """
    Managed order with full lifecycle tracking.

    Tracks order from creation through completion.
    """
    # Order identification (required)
    order_id: str
    client_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float

    # Optional fields with defaults
    exchange_order_id: Optional[str] = None
    price: Optional[float] = None

    # Exchange info
    exchange: str = "binance"
    market_type: str = "spot"

    # State tracking
    state: OrderState = OrderState.PENDING
    status: OrderStatus = OrderStatus.PENDING

    # Fill information
    filled_quantity: float = 0.0
    avg_fill_price: Optional[float] = None
    remaining_quantity: Optional[float] = None

    # Fees
    commission: float = 0.0
    commission_asset: str = "USDT"

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    # Link to signal
    signal_id: Optional[str] = None

    # Retry tracking
    retry_count: int = 0
    last_error: Optional[str] = None

    # Metadata
    metadata: Dict = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """Check if order is active."""
        return self.state in [OrderState.SUBMITTED, OrderState.ACTIVE, OrderState.PARTIALLY_FILLED]

    @property
    def is_terminal(self) -> bool:
        """Check if order is in terminal state."""
        return self.state in [OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED, OrderState.FAILED]

    @property
    def fill_percentage(self) -> float:
        """Get fill percentage."""
        if self.quantity == 0:
            return 0.0
        return (self.filled_quantity / self.quantity) * 100


class OrderManager:
    """
    Order manager for tracking order lifecycle.

    Features:
    - Track all pending and active orders
    - Update order state from exchange
    - Query orders by various criteria
    - Order history management
    """

    def __init__(self, max_history_size: int = 1000):
        """
        Initialize order manager.

        Args:
            max_history_size: Maximum number of completed orders to keep in history
        """
        self.max_history_size = max_history_size

        # Active orders (by client order ID)
        self._active_orders: Dict[str, ManagedOrder] = {}

        # Order history (completed orders)
        self._order_history: List[ManagedOrder] = []

        # Index by exchange order ID for quick lookup
        self._exchange_order_index: Dict[str, str] = {}  # exchange_order_id -> client_order_id

    def create_order(
        self,
        client_order_id: str,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        exchange: str = "binance",
        market_type: str = "spot",
        signal_id: Optional[str] = None,
        **metadata
    ) -> ManagedOrder:
        """
        Create and track a new order.

        Args:
            client_order_id: Client order ID
            symbol: Trading symbol
            side: Order side
            order_type: Order type
            quantity: Order quantity
            price: Order price
            exchange: Exchange name
            market_type: Market type
            signal_id: Associated signal ID
            **metadata: Additional metadata

        Returns:
            Managed order
        """
        order = ManagedOrder(
            order_id=client_order_id,
            client_order_id=client_order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            exchange=exchange,
            market_type=market_type,
            signal_id=signal_id,
            metadata=metadata
        )

        self._active_orders[client_order_id] = order

        logger.info(
            f"Created order: {client_order_id} ({symbol} {side.value} {quantity} @ {price})"
        )

        return order

    def update_order_submitted(
        self,
        client_order_id: str,
        exchange_order_id: str
    ) -> Optional[ManagedOrder]:
        """
        Update order when submitted to exchange.

        Args:
            client_order_id: Client order ID
            exchange_order_id: Exchange order ID

        Returns:
            Updated order or None if not found
        """
        order = self._active_orders.get(client_order_id)
        if order is None:
            logger.warning(f"Order not found: {client_order_id}")
            return None

        order.exchange_order_id = exchange_order_id
        order.state = OrderState.SUBMITTED
        order.status = OrderStatus.PLACED
        order.submitted_at = datetime.utcnow()

        # Index by exchange order ID
        self._exchange_order_index[exchange_order_id] = client_order_id

        logger.info(f"Order submitted: {client_order_id} -> {exchange_order_id}")

        return order

    def update_order_filled(
        self,
        client_order_id: str,
        filled_quantity: float,
        avg_fill_price: float,
        commission: float = 0.0,
        commission_asset: str = "USDT",
        is_partial: bool = False
    ) -> Optional[ManagedOrder]:
        """
        Update order when filled.

        Args:
            client_order_id: Client order ID
            filled_quantity: Filled quantity
            avg_fill_price: Average fill price
            commission: Commission paid
            commission_asset: Commission asset
            is_partial: Whether this is a partial fill

        Returns:
            Updated order or None if not found
        """
        order = self._active_orders.get(client_order_id)
        if order is None:
            logger.warning(f"Order not found: {client_order_id}")
            return None

        order.filled_quantity = filled_quantity
        order.avg_fill_price = avg_fill_price
        order.commission = commission
        order.commission_asset = commission_asset
        order.remaining_quantity = order.quantity - filled_quantity

        if is_partial:
            order.state = OrderState.PARTIALLY_FILLED
            order.status = OrderStatus.PARTIALLY_FILLED
            logger.info(
                f"Order partially filled: {client_order_id} "
                f"({filled_quantity}/{order.quantity} @ {avg_fill_price})"
            )
        else:
            order.state = OrderState.FILLED
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.utcnow()
            logger.info(
                f"Order filled: {client_order_id} "
                f"({filled_quantity} @ {avg_fill_price})"
            )

            # Move to history
            self._move_to_history(order)

        return order

    def update_order_failed(
        self,
        client_order_id: str,
        error: str,
        is_rejected: bool = False
    ) -> Optional[ManagedOrder]:
        """
        Update order when failed.

        Args:
            client_order_id: Client order ID
            error: Error message
            is_rejected: Whether order was rejected

        Returns:
            Updated order or None if not found
        """
        order = self._active_orders.get(client_order_id)
        if order is None:
            logger.warning(f"Order not found: {client_order_id}")
            return None

        order.state = OrderState.REJECTED if is_rejected else OrderState.FAILED
        order.status = OrderStatus.REJECTED if is_rejected else OrderStatus.FAILED
        order.last_error = error

        logger.error(f"Order failed: {client_order_id} - {error}")

        # Move to history
        self._move_to_history(order)

        return order

    def update_order_cancelled(self, client_order_id: str) -> Optional[ManagedOrder]:
        """
        Update order when cancelled.

        Args:
            client_order_id: Client order ID

        Returns:
            Updated order or None if not found
        """
        order = self._active_orders.get(client_order_id)
        if order is None:
            logger.warning(f"Order not found: {client_order_id}")
            return None

        order.state = OrderState.CANCELLED
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = datetime.utcnow()

        logger.info(f"Order cancelled: {client_order_id}")

        # Move to history
        self._move_to_history(order)

        return order

    def get_order(self, client_order_id: str) -> Optional[ManagedOrder]:
        """
        Get order by client order ID.

        Args:
            client_order_id: Client order ID

        Returns:
            Order or None if not found
        """
        return self._active_orders.get(client_order_id)

    def get_order_by_exchange_id(self, exchange_order_id: str) -> Optional[ManagedOrder]:
        """
        Get order by exchange order ID.

        Args:
            exchange_order_id: Exchange order ID

        Returns:
            Order or None if not found
        """
        client_order_id = self._exchange_order_index.get(exchange_order_id)
        if client_order_id:
            return self._active_orders.get(client_order_id)
        return None

    def get_active_orders(self, symbol: Optional[str] = None) -> List[ManagedOrder]:
        """
        Get all active orders.

        Args:
            symbol: Filter by symbol

        Returns:
            List of active orders
        """
        orders = list(self._active_orders.values())

        if symbol:
            orders = [o for o in orders if o.symbol == symbol]

        return orders

    def get_order_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[ManagedOrder]:
        """
        Get order history.

        Args:
            symbol: Filter by symbol
            limit: Maximum number of orders to return

        Returns:
            List of completed orders (most recent first)
        """
        orders = self._order_history[-limit:]

        if symbol:
            orders = [o for o in orders if o.symbol == symbol]

        return list(reversed(orders))

    def _move_to_history(self, order: ManagedOrder):
        """
        Move order from active to history.

        Args:
            order: Order to move
        """
        # Remove from active
        self._active_orders.pop(order.client_order_id, None)

        # Remove from exchange index
        if order.exchange_order_id:
            self._exchange_order_index.pop(order.exchange_order_id, None)

        # Add to history
        self._order_history.append(order)

        # Trim history if too large
        if len(self._order_history) > self.max_history_size:
            self._order_history = self._order_history[-self.max_history_size:]

    def get_stats(self) -> Dict:
        """
        Get order manager statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "active_orders": len(self._active_orders),
            "history_size": len(self._order_history),
            "total_orders": len(self._active_orders) + len(self._order_history),
        }
