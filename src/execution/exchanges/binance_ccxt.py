"""
Binance exchange adapter using CCXT library.

Provides integration with Binance exchange via CCXT with
rate limiting, error handling, and retry logic.
"""

import logging
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

try:
    import ccxt.async_support as ccxt
except ImportError:
    # Fallback if ccxt not installed
    ccxt = None

from src.execution.exchanges.base import (
    ExchangeAdapter,
    Balance,
    Position,
    OrderInfo,
    ExchangeError,
    RateLimitError,
    InsufficientBalanceError,
    OrderNotFoundError,
    InvalidOrderError
)
from src.core.events import OrderSide, OrderType, OrderStatus

logger = logging.getLogger(__name__)


class BinanceCCXTAdapter(ExchangeAdapter):
    """
    Binance exchange adapter using CCXT.

    Features:
    - Automatic rate limiting via CCXT
    - Error handling and classification
    - Support for spot and futures markets
    - Unified interface for order management
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = False,
        market_type: str = "spot",
        rate_limit: bool = True,
        **kwargs
    ):
        """
        Initialize Binance CCXT adapter.

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Whether to use testnet
            market_type: Market type ('spot' or 'futures')
            rate_limit: Enable rate limiting
        """
        super().__init__(api_key, api_secret, testnet)

        if ccxt is None:
            raise ImportError("CCXT library not installed. Install with: pip install ccxt")

        self.market_type = market_type
        self.rate_limit = rate_limit
        self._exchange: Optional[ccxt.binance] = None

    async def connect(self) -> bool:
        """
        Connect to Binance via CCXT.

        Returns:
            True if connected successfully
        """
        try:
            config = {
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': self.rate_limit,
                'options': {
                    'defaultType': self.market_type,
                }
            }

            if self.testnet:
                config['urls'] = {
                    'api': {
                        'public': 'https://testnet.binance.vision/api',
                        'private': 'https://testnet.binance.vision/api',
                    }
                }

            self._exchange = ccxt.binance(config)

            # Load markets
            await self._exchange.load_markets()

            self._connected = True
            logger.info(f"Connected to Binance {self.market_type} (testnet={self.testnet})")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Binance: {e}")
            raise ExchangeError(f"Connection failed: {str(e)}")

    async def disconnect(self) -> None:
        """Disconnect from Binance."""
        if self._exchange:
            await self._exchange.close()
            self._connected = False
            logger.info("Disconnected from Binance")

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
        Place order on Binance.

        Args:
            symbol: Trading symbol
            side: Order side
            order_type: Order type
            quantity: Order quantity
            price: Limit price
            stop_price: Stop price
            client_order_id: Client order ID
            time_in_force: Time in force
            **kwargs: Additional parameters

        Returns:
            Order information
        """
        self._ensure_connected()

        try:
            # Convert enums to CCXT format
            ccxt_side = side.value.lower()
            ccxt_type = self._convert_order_type(order_type)

            # Generate client order ID if not provided
            if client_order_id is None:
                client_order_id = f"order_{uuid.uuid4().hex[:16]}"

            # Build order parameters
            params = {
                'newClientOrderId': client_order_id,
                **kwargs
            }

            # Add time in force for limit orders
            if order_type == OrderType.LIMIT:
                params['timeInForce'] = time_in_force

            # Place order
            logger.info(
                f"Placing {ccxt_type} {ccxt_side} order: {symbol} "
                f"qty={quantity} price={price}"
            )

            if order_type == OrderType.MARKET:
                result = await self._exchange.create_market_order(
                    symbol=symbol,
                    side=ccxt_side,
                    amount=quantity,
                    params=params
                )
            elif order_type == OrderType.LIMIT:
                result = await self._exchange.create_limit_order(
                    symbol=symbol,
                    side=ccxt_side,
                    amount=quantity,
                    price=price,
                    params=params
                )
            elif order_type == OrderType.STOP_LOSS:
                result = await self._exchange.create_order(
                    symbol=symbol,
                    type='stop_market',
                    side=ccxt_side,
                    amount=quantity,
                    params={'stopPrice': stop_price, **params}
                )
            else:
                raise InvalidOrderError(f"Unsupported order type: {order_type}")

            # Convert result to OrderInfo
            order_info = self._parse_order(result, symbol, side, order_type)

            logger.info(
                f"Order placed: {order_info.order_id} "
                f"(status={order_info.status}, filled={order_info.filled_quantity})"
            )

            return order_info

        except ccxt.InsufficientFunds as e:
            logger.error(f"Insufficient balance: {e}")
            raise InsufficientBalanceError(str(e))
        except ccxt.RateLimitExceeded as e:
            logger.warning(f"Rate limit exceeded: {e}")
            raise RateLimitError(str(e))
        except ccxt.InvalidOrder as e:
            logger.error(f"Invalid order: {e}")
            raise InvalidOrderError(str(e))
        except ccxt.BaseError as e:
            logger.error(f"Exchange error: {e}")
            raise ExchangeError(str(e))

    async def cancel_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> bool:
        """Cancel order."""
        self._ensure_connected()

        try:
            params = {}
            if client_order_id:
                params['origClientOrderId'] = client_order_id

            await self._exchange.cancel_order(
                id=order_id,
                symbol=symbol,
                params=params
            )

            logger.info(f"Order cancelled: {order_id or client_order_id}")
            return True

        except ccxt.OrderNotFound as e:
            logger.warning(f"Order not found: {e}")
            raise OrderNotFoundError(str(e))
        except ccxt.BaseError as e:
            logger.error(f"Cancel order failed: {e}")
            raise ExchangeError(str(e))

    async def get_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> OrderInfo:
        """Get order information."""
        self._ensure_connected()

        try:
            params = {}
            if client_order_id:
                params['origClientOrderId'] = client_order_id

            result = await self._exchange.fetch_order(
                id=order_id,
                symbol=symbol,
                params=params
            )

            return self._parse_order(result, symbol)

        except ccxt.OrderNotFound as e:
            raise OrderNotFoundError(str(e))
        except ccxt.BaseError as e:
            raise ExchangeError(str(e))

    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, Balance]:
        """Get account balance."""
        self._ensure_connected()

        try:
            result = await self._exchange.fetch_balance()

            balances = {}
            for currency, balance in result['total'].items():
                if asset and currency != asset:
                    continue

                balances[currency] = Balance(
                    asset=currency,
                    free=result['free'].get(currency, 0.0),
                    locked=result['used'].get(currency, 0.0),
                    total=balance
                )

            return balances

        except ccxt.BaseError as e:
            raise ExchangeError(str(e))

    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """Get open positions (futures only)."""
        self._ensure_connected()

        if self.market_type != 'futures':
            return []

        try:
            result = await self._exchange.fetch_positions(symbols=[symbol] if symbol else None)

            positions = []
            for pos in result:
                if pos['contracts'] == 0:
                    continue

                positions.append(Position(
                    symbol=pos['symbol'],
                    side='long' if pos['side'] == 'long' else 'short',
                    size=abs(pos['contracts']),
                    entry_price=pos['entryPrice'],
                    current_price=pos['markPrice'],
                    unrealized_pnl=pos['unrealizedPnl'],
                    leverage=pos.get('leverage', 1.0)
                ))

            return positions

        except ccxt.BaseError as e:
            raise ExchangeError(str(e))

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get ticker information."""
        self._ensure_connected()

        try:
            ticker = await self._exchange.fetch_ticker(symbol)
            return ticker
        except ccxt.BaseError as e:
            raise ExchangeError(str(e))

    async def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """Get symbol information."""
        self._ensure_connected()

        try:
            market = self._exchange.market(symbol)
            return market
        except Exception as e:
            raise ExchangeError(str(e))

    def get_exchange_name(self) -> str:
        """Get exchange name."""
        return "binance"

    def _ensure_connected(self):
        """Ensure exchange is connected."""
        if not self._connected or self._exchange is None:
            raise ExchangeError("Not connected to exchange")

    def _convert_order_type(self, order_type: OrderType) -> str:
        """Convert OrderType enum to CCXT format."""
        mapping = {
            OrderType.MARKET: 'market',
            OrderType.LIMIT: 'limit',
            OrderType.STOP_LOSS: 'stop_market',
            OrderType.STOP_LIMIT: 'stop_limit',
        }
        return mapping.get(order_type, 'market')

    def _convert_order_status(self, ccxt_status: str) -> OrderStatus:
        """Convert CCXT order status to OrderStatus enum."""
        mapping = {
            'open': OrderStatus.PLACED,
            'closed': OrderStatus.FILLED,
            'canceled': OrderStatus.CANCELLED,
            'expired': OrderStatus.CANCELLED,
            'rejected': OrderStatus.REJECTED,
        }
        return mapping.get(ccxt_status, OrderStatus.PENDING)

    def _parse_order(
        self,
        result: Dict[str, Any],
        symbol: str,
        side: Optional[OrderSide] = None,
        order_type: Optional[OrderType] = None
    ) -> OrderInfo:
        """Parse CCXT order result into OrderInfo."""
        # Extract order side
        if side is None:
            side = OrderSide.BUY if result['side'] == 'buy' else OrderSide.SELL

        # Extract order type
        if order_type is None:
            order_type = OrderType.MARKET if result['type'] == 'market' else OrderType.LIMIT

        return OrderInfo(
            order_id=str(result['id']),
            client_order_id=result.get('clientOrderId'),
            symbol=symbol,
            side=side,
            order_type=order_type,
            status=self._convert_order_status(result['status']),
            price=result.get('price'),
            quantity=result['amount'],
            filled_quantity=result['filled'],
            avg_fill_price=result.get('average'),
            commission=result.get('fee', {}).get('cost', 0.0),
            commission_asset=result.get('fee', {}).get('currency', 'USDT'),
            created_at=datetime.fromtimestamp(result['timestamp'] / 1000) if result.get('timestamp') else datetime.utcnow(),
            updated_at=datetime.fromtimestamp(result.get('lastTradeTimestamp', result['timestamp']) / 1000) if result.get('timestamp') else datetime.utcnow(),
            raw_data=result
        )
