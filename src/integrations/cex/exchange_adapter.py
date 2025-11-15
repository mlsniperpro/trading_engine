"""
Centralized Exchange (CEX) Adapter - Abstract Base Class.

This module defines the standard interface for all CEX integrations:
- ExchangeAdapter: Abstract base class for exchange implementations
- Order, Balance, Position models
- Standard exception classes

Supported exchanges:
- Binance (Spot & Futures)
- Bybit (Spot & Futures)
- Hyperliquid (Perpetuals)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from datetime import datetime


# ============================================================================
# Enums
# ============================================================================

class OrderSide(str, Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LOSS_LIMIT = "stop_loss_limit"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TimeInForce(str, Enum):
    """Time in force."""
    GTC = "GTC"  # Good Till Cancel
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill


class PositionSide(str, Enum):
    """Position side (for futures)."""
    LONG = "long"
    SHORT = "short"
    BOTH = "both"  # Hedge mode


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class Ticker:
    """Market ticker data."""
    symbol: str
    bid: Decimal  # Best bid price
    ask: Decimal  # Best ask price
    last: Decimal  # Last traded price
    volume_24h: Optional[Decimal] = None
    high_24h: Optional[Decimal] = None
    low_24h: Optional[Decimal] = None
    timestamp: Optional[datetime] = None


@dataclass
class Balance:
    """Account balance."""
    asset: str
    free: Decimal  # Available balance
    locked: Decimal  # Locked balance (in orders)
    total: Decimal  # Total balance
    usd_value: Optional[Decimal] = None


@dataclass
class Order:
    """Order information."""
    order_id: str
    symbol: str
    side: OrderSide
    type: OrderType
    status: OrderStatus

    # Amounts
    quantity: Decimal  # Original order quantity
    filled_quantity: Decimal  # Filled quantity
    remaining_quantity: Decimal  # Remaining quantity

    # Prices
    price: Optional[Decimal] = None  # Limit price (None for market orders)
    average_fill_price: Optional[Decimal] = None  # Average fill price
    stop_price: Optional[Decimal] = None  # Stop price (for stop orders)

    # Timing
    time_in_force: TimeInForce = TimeInForce.GTC
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Fees
    fee: Optional[Decimal] = None
    fee_asset: Optional[str] = None

    # Raw data from exchange
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class Position:
    """Futures position information."""
    symbol: str
    side: PositionSide
    size: Decimal  # Position size
    entry_price: Decimal  # Average entry price
    mark_price: Optional[Decimal] = None  # Current mark price
    liquidation_price: Optional[Decimal] = None

    # P&L
    unrealized_pnl: Optional[Decimal] = None
    realized_pnl: Optional[Decimal] = None

    # Leverage
    leverage: Optional[int] = None
    margin: Optional[Decimal] = None  # Margin used

    # Timing
    opened_at: Optional[datetime] = None

    # Raw data from exchange
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class Trade:
    """Trade execution information."""
    trade_id: str
    order_id: str
    symbol: str
    side: OrderSide
    price: Decimal
    quantity: Decimal
    fee: Optional[Decimal] = None
    fee_asset: Optional[str] = None
    timestamp: Optional[datetime] = None
    is_maker: bool = False


# ============================================================================
# Exchange Adapter Abstract Base Class
# ============================================================================

class ExchangeAdapter(ABC):
    """
    Abstract base class for centralized exchange adapters.

    All exchange implementations must inherit from this class and
    implement the required methods.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False
    ):
        """
        Initialize exchange adapter.

        Args:
            api_key: Exchange API key
            api_secret: Exchange API secret
            testnet: Use testnet/sandbox environment
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        """
        Get current ticker for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            Ticker with current prices

        Raises:
            Exception: If ticker fetch fails
        """
        pass

    @abstractmethod
    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, Balance]:
        """
        Get account balance(s).

        Args:
            asset: Specific asset to get balance for (None for all)

        Returns:
            Dictionary mapping asset symbols to Balance objects

        Raises:
            Exception: If balance fetch fails
        """
        pass

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        **kwargs
    ) -> Order:
        """
        Place an order.

        Args:
            symbol: Trading pair symbol
            side: Order side (buy/sell)
            type: Order type (market/limit/etc.)
            quantity: Order quantity
            price: Limit price (required for limit orders)
            time_in_force: Time in force
            **kwargs: Additional exchange-specific parameters

        Returns:
            Order object with order details

        Raises:
            Exception: If order placement fails
        """
        pass

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> Order:
        """
        Cancel an open order.

        Args:
            symbol: Trading pair symbol
            order_id: Order ID to cancel

        Returns:
            Canceled Order object

        Raises:
            Exception: If order cancellation fails
        """
        pass

    @abstractmethod
    async def get_order(self, symbol: str, order_id: str) -> Order:
        """
        Get order information.

        Args:
            symbol: Trading pair symbol
            order_id: Order ID

        Returns:
            Order object

        Raises:
            Exception: If order fetch fails
        """
        pass

    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        Get all open orders.

        Args:
            symbol: Filter by symbol (None for all symbols)

        Returns:
            List of open Order objects

        Raises:
            Exception: If fetch fails
        """
        pass

    @abstractmethod
    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """
        Get open positions (for futures/margin trading).

        Args:
            symbol: Filter by symbol (None for all symbols)

        Returns:
            List of Position objects

        Raises:
            Exception: If fetch fails
        """
        pass

    @abstractmethod
    async def close_position(
        self,
        symbol: str,
        side: Optional[PositionSide] = None
    ) -> Order:
        """
        Close a position (for futures/margin trading).

        Args:
            symbol: Trading pair symbol
            side: Position side to close (None to close all)

        Returns:
            Order object for the closing order

        Raises:
            Exception: If position close fails
        """
        pass

    @abstractmethod
    async def get_trades(
        self,
        symbol: str,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Trade]:
        """
        Get trade history.

        Args:
            symbol: Trading pair symbol
            limit: Maximum number of trades to return
            start_time: Start time filter
            end_time: End time filter

        Returns:
            List of Trade objects

        Raises:
            Exception: If fetch fails
        """
        pass

    async def health_check(self) -> bool:
        """
        Check if exchange API is healthy and accessible.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Try to fetch server time or ping
            await self.get_server_time()
            return True
        except Exception:
            return False

    @abstractmethod
    async def get_server_time(self) -> datetime:
        """
        Get exchange server time.

        Returns:
            Server timestamp

        Raises:
            Exception: If fetch fails
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get exchange name.

        Returns:
            Exchange name (e.g., 'binance', 'bybit')
        """
        pass

    @property
    @abstractmethod
    def supports_futures(self) -> bool:
        """
        Check if exchange supports futures trading.

        Returns:
            True if futures supported
        """
        pass

    def __repr__(self) -> str:
        """String representation of adapter."""
        return f"{self.__class__.__name__}(name={self.name}, testnet={self.testnet})"


# ============================================================================
# Exception Classes
# ============================================================================

class ExchangeError(Exception):
    """Base exception for exchange errors."""
    pass


class AuthenticationError(ExchangeError):
    """Exception raised for authentication failures."""
    pass


class InsufficientBalanceError(ExchangeError):
    """Exception raised when account has insufficient balance."""
    pass


class OrderError(ExchangeError):
    """Exception raised for order-related errors."""
    pass


class RateLimitError(ExchangeError):
    """Exception raised when rate limit is exceeded."""
    pass


class NetworkError(ExchangeError):
    """Exception raised for network/connectivity errors."""
    pass
