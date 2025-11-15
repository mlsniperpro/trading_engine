"""
Exchange adapter base class.

Defines the interface for exchange integrations using the adapter pattern.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from src.core.events import OrderSide, OrderType, OrderStatus


@dataclass
class Balance:
    """Account balance information."""
    asset: str
    free: float
    locked: float
    total: float


@dataclass
class Position:
    """Position information."""
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    leverage: float = 1.0


@dataclass
class OrderInfo:
    """Order information returned from exchange."""
    order_id: str
    client_order_id: Optional[str]
    symbol: str
    side: OrderSide
    order_type: OrderType
    status: OrderStatus
    price: Optional[float]
    quantity: float
    filled_quantity: float
    avg_fill_price: Optional[float]
    commission: float
    commission_asset: str
    created_at: datetime
    updated_at: datetime
    raw_data: Dict[str, Any]


class ExchangeAdapter(ABC):
    """
    Abstract base class for exchange adapters.

    Provides a unified interface for different exchanges,
    abstracting away exchange-specific API differences.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = False
    ):
        """
        Initialize exchange adapter.

        Args:
            api_key: API key
            api_secret: API secret
            testnet: Whether to use testnet
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self._connected = False

    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to exchange.

        Returns:
            True if connected successfully
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from exchange."""
        pass

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        client_order_id: Optional[str] = None,
        time_in_force: str = "GTC",
        **kwargs
    ) -> OrderInfo:
        """
        Place an order on the exchange.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            side: Order side (BUY or SELL)
            order_type: Order type (MARKET, LIMIT, etc.)
            quantity: Order quantity
            price: Limit price (required for LIMIT orders)
            stop_price: Stop price (for STOP_LOSS orders)
            client_order_id: Client-specified order ID
            time_in_force: Time in force (GTC, IOC, FOK)
            **kwargs: Additional exchange-specific parameters

        Returns:
            Order information

        Raises:
            ExchangeError: If order placement fails
        """
        pass

    @abstractmethod
    async def cancel_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> bool:
        """
        Cancel an order.

        Args:
            symbol: Trading symbol
            order_id: Exchange order ID
            client_order_id: Client order ID

        Returns:
            True if cancelled successfully

        Raises:
            ExchangeError: If cancellation fails
        """
        pass

    @abstractmethod
    async def get_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> OrderInfo:
        """
        Get order information.

        Args:
            symbol: Trading symbol
            order_id: Exchange order ID
            client_order_id: Client order ID

        Returns:
            Order information

        Raises:
            ExchangeError: If order not found
        """
        pass

    @abstractmethod
    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, Balance]:
        """
        Get account balance.

        Args:
            asset: Specific asset to query (e.g., 'USDT'), or None for all

        Returns:
            Dictionary of asset -> Balance

        Raises:
            ExchangeError: If balance query fails
        """
        pass

    @abstractmethod
    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """
        Get open positions (for futures/margin).

        Args:
            symbol: Specific symbol to query, or None for all

        Returns:
            List of positions

        Raises:
            ExchangeError: If position query fails
        """
        pass

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Get current ticker/price information.

        Args:
            symbol: Trading symbol

        Returns:
            Ticker information (bid, ask, last, volume, etc.)

        Raises:
            ExchangeError: If ticker query fails
        """
        pass

    @abstractmethod
    async def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """
        Get symbol/market information.

        Args:
            symbol: Trading symbol

        Returns:
            Symbol information (min qty, price precision, etc.)

        Raises:
            ExchangeError: If symbol not found
        """
        pass

    @property
    def is_connected(self) -> bool:
        """Check if connected to exchange."""
        return self._connected

    @abstractmethod
    def get_exchange_name(self) -> str:
        """Get exchange name."""
        pass


class ExchangeError(Exception):
    """Base exception for exchange errors."""
    def __init__(self, message: str, error_code: Optional[str] = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class RateLimitError(ExchangeError):
    """Rate limit exceeded error."""
    pass


class InsufficientBalanceError(ExchangeError):
    """Insufficient balance error."""
    pass


class OrderNotFoundError(ExchangeError):
    """Order not found error."""
    pass


class InvalidOrderError(ExchangeError):
    """Invalid order parameters error."""
    pass
