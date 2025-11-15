"""
Binance Exchange Adapter.

Implementation of ExchangeAdapter for Binance (Spot & Futures).

Features:
- Spot trading support
- Futures trading support
- CCXT library integration
- Rate limit handling
- Unified interface
"""

from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
import ccxt
import logging

from .exchange_adapter import (
    ExchangeAdapter,
    Ticker,
    Balance,
    Order,
    Position,
    Trade,
    OrderSide,
    OrderType,
    OrderStatus,
    TimeInForce,
    PositionSide,
    ExchangeError,
    AuthenticationError,
    InsufficientBalanceError,
    OrderError,
    RateLimitError,
    NetworkError,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Binance Adapter
# ============================================================================

class BinanceAdapter(ExchangeAdapter):
    """
    Binance exchange adapter using CCXT library.

    Supports both spot and futures trading with unified interface.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        market_type: str = "spot",  # "spot" or "futures"
        testnet: bool = False
    ):
        """
        Initialize Binance adapter.

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            market_type: Market type ("spot" or "futures")
            testnet: Use testnet environment
        """
        super().__init__(api_key, api_secret, testnet)

        self.market_type = market_type

        # Initialize CCXT exchange
        if market_type == "futures":
            self.exchange = ccxt.binanceusdm({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                },
            })
        else:
            self.exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
            })

        # Set testnet if requested
        if testnet:
            self.exchange.set_sandbox_mode(True)

        logger.info(f"BinanceAdapter initialized (market={market_type}, testnet={testnet})")

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get current ticker for a symbol."""
        try:
            ticker_data = await self.exchange.fetch_ticker(symbol)

            return Ticker(
                symbol=symbol,
                bid=Decimal(str(ticker_data['bid'])),
                ask=Decimal(str(ticker_data['ask'])),
                last=Decimal(str(ticker_data['last'])),
                volume_24h=Decimal(str(ticker_data.get('baseVolume', 0))),
                high_24h=Decimal(str(ticker_data.get('high', 0))),
                low_24h=Decimal(str(ticker_data.get('low', 0))),
                timestamp=datetime.fromtimestamp(ticker_data['timestamp'] / 1000) if ticker_data.get('timestamp') else None
            )
        except ccxt.AuthenticationError as e:
            raise AuthenticationError(f"Authentication failed: {e}")
        except ccxt.NetworkError as e:
            raise NetworkError(f"Network error: {e}")
        except Exception as e:
            raise ExchangeError(f"Failed to get ticker: {e}")

    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, Balance]:
        """Get account balance(s)."""
        try:
            balance_data = await self.exchange.fetch_balance()

            balances = {}
            for asset_symbol, amounts in balance_data['total'].items():
                if amounts > 0:  # Only include non-zero balances
                    balances[asset_symbol] = Balance(
                        asset=asset_symbol,
                        free=Decimal(str(balance_data['free'].get(asset_symbol, 0))),
                        locked=Decimal(str(balance_data['used'].get(asset_symbol, 0))),
                        total=Decimal(str(amounts))
                    )

            if asset:
                return {asset: balances.get(asset, Balance(asset, Decimal(0), Decimal(0), Decimal(0)))}

            return balances

        except ccxt.AuthenticationError as e:
            raise AuthenticationError(f"Authentication failed: {e}")
        except ccxt.NetworkError as e:
            raise NetworkError(f"Network error: {e}")
        except Exception as e:
            raise ExchangeError(f"Failed to get balance: {e}")

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
        """Place an order."""
        try:
            # Convert to CCXT format
            ccxt_side = side.value
            ccxt_type = type.value.replace("_", "-")  # CCXT uses hyphens

            # Prepare params
            params = {
                'timeInForce': time_in_force.value,
            }
            params.update(kwargs)

            # Place order
            if type == OrderType.MARKET:
                order_data = await self.exchange.create_order(
                    symbol=symbol,
                    type=ccxt_type,
                    side=ccxt_side,
                    amount=float(quantity),
                    params=params
                )
            else:
                if price is None:
                    raise OrderError("Price required for limit orders")

                order_data = await self.exchange.create_order(
                    symbol=symbol,
                    type=ccxt_type,
                    side=ccxt_side,
                    amount=float(quantity),
                    price=float(price),
                    params=params
                )

            # Convert to Order object
            return self._parse_order(order_data)

        except ccxt.InsufficientFunds as e:
            raise InsufficientBalanceError(f"Insufficient balance: {e}")
        except ccxt.AuthenticationError as e:
            raise AuthenticationError(f"Authentication failed: {e}")
        except ccxt.NetworkError as e:
            raise NetworkError(f"Network error: {e}")
        except Exception as e:
            raise OrderError(f"Failed to place order: {e}")

    async def cancel_order(self, symbol: str, order_id: str) -> Order:
        """Cancel an open order."""
        try:
            order_data = await self.exchange.cancel_order(order_id, symbol)
            return self._parse_order(order_data)

        except ccxt.AuthenticationError as e:
            raise AuthenticationError(f"Authentication failed: {e}")
        except ccxt.NetworkError as e:
            raise NetworkError(f"Network error: {e}")
        except Exception as e:
            raise OrderError(f"Failed to cancel order: {e}")

    async def get_order(self, symbol: str, order_id: str) -> Order:
        """Get order information."""
        try:
            order_data = await self.exchange.fetch_order(order_id, symbol)
            return self._parse_order(order_data)

        except ccxt.AuthenticationError as e:
            raise AuthenticationError(f"Authentication failed: {e}")
        except ccxt.NetworkError as e:
            raise NetworkError(f"Network error: {e}")
        except Exception as e:
            raise OrderError(f"Failed to get order: {e}")

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get all open orders."""
        try:
            orders_data = await self.exchange.fetch_open_orders(symbol)
            return [self._parse_order(order_data) for order_data in orders_data]

        except ccxt.AuthenticationError as e:
            raise AuthenticationError(f"Authentication failed: {e}")
        except ccxt.NetworkError as e:
            raise NetworkError(f"Network error: {e}")
        except Exception as e:
            raise ExchangeError(f"Failed to get open orders: {e}")

    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """Get open positions (futures only)."""
        if self.market_type != "futures":
            return []

        try:
            positions_data = await self.exchange.fetch_positions(symbols=[symbol] if symbol else None)

            positions = []
            for pos_data in positions_data:
                # Only include positions with size > 0
                if float(pos_data.get('contracts', 0)) > 0:
                    positions.append(self._parse_position(pos_data))

            return positions

        except ccxt.AuthenticationError as e:
            raise AuthenticationError(f"Authentication failed: {e}")
        except ccxt.NetworkError as e:
            raise NetworkError(f"Network error: {e}")
        except Exception as e:
            raise ExchangeError(f"Failed to get positions: {e}")

    async def close_position(
        self,
        symbol: str,
        side: Optional[PositionSide] = None
    ) -> Order:
        """Close a position (futures only)."""
        if self.market_type != "futures":
            raise ExchangeError("Position closing only available for futures")

        try:
            # Get current position
            positions = await self.get_positions(symbol)

            if not positions:
                raise OrderError(f"No open position for {symbol}")

            position = positions[0]

            # Determine closing side (opposite of position)
            if position.side == PositionSide.LONG:
                close_side = OrderSide.SELL
            else:
                close_side = OrderSide.BUY

            # Place market order to close
            return await self.place_order(
                symbol=symbol,
                side=close_side,
                type=OrderType.MARKET,
                quantity=abs(position.size),
                reduceOnly=True  # Ensure it's a closing order
            )

        except ccxt.AuthenticationError as e:
            raise AuthenticationError(f"Authentication failed: {e}")
        except ccxt.NetworkError as e:
            raise NetworkError(f"Network error: {e}")
        except Exception as e:
            raise OrderError(f"Failed to close position: {e}")

    async def get_trades(
        self,
        symbol: str,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Trade]:
        """Get trade history."""
        try:
            params = {}
            if start_time:
                params['startTime'] = int(start_time.timestamp() * 1000)
            if end_time:
                params['endTime'] = int(end_time.timestamp() * 1000)

            trades_data = await self.exchange.fetch_my_trades(symbol, limit=limit, params=params)

            return [self._parse_trade(trade_data) for trade_data in trades_data]

        except ccxt.AuthenticationError as e:
            raise AuthenticationError(f"Authentication failed: {e}")
        except ccxt.NetworkError as e:
            raise NetworkError(f"Network error: {e}")
        except Exception as e:
            raise ExchangeError(f"Failed to get trades: {e}")

    async def get_server_time(self) -> datetime:
        """Get exchange server time."""
        try:
            server_time = await self.exchange.fetch_time()
            return datetime.fromtimestamp(server_time / 1000)
        except Exception as e:
            raise ExchangeError(f"Failed to get server time: {e}")

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _parse_order(self, order_data: Dict[str, Any]) -> Order:
        """Parse CCXT order data into Order object."""
        return Order(
            order_id=str(order_data['id']),
            symbol=order_data['symbol'],
            side=OrderSide(order_data['side']),
            type=OrderType(order_data['type'].replace("-", "_")),
            status=self._parse_order_status(order_data['status']),
            quantity=Decimal(str(order_data['amount'])),
            filled_quantity=Decimal(str(order_data.get('filled', 0))),
            remaining_quantity=Decimal(str(order_data.get('remaining', 0))),
            price=Decimal(str(order_data['price'])) if order_data.get('price') else None,
            average_fill_price=Decimal(str(order_data.get('average'))) if order_data.get('average') else None,
            time_in_force=TimeInForce(order_data.get('timeInForce', 'GTC')),
            created_at=datetime.fromtimestamp(order_data['timestamp'] / 1000) if order_data.get('timestamp') else None,
            fee=Decimal(str(order_data['fee']['cost'])) if order_data.get('fee') else None,
            fee_asset=order_data['fee']['currency'] if order_data.get('fee') else None,
            raw_data=order_data
        )

    def _parse_order_status(self, status: str) -> OrderStatus:
        """Parse CCXT order status to OrderStatus enum."""
        status_map = {
            'open': OrderStatus.OPEN,
            'closed': OrderStatus.FILLED,
            'canceled': OrderStatus.CANCELED,
            'expired': OrderStatus.EXPIRED,
            'rejected': OrderStatus.REJECTED,
        }
        return status_map.get(status, OrderStatus.PENDING)

    def _parse_position(self, pos_data: Dict[str, Any]) -> Position:
        """Parse CCXT position data into Position object."""
        side = PositionSide.LONG if float(pos_data.get('contracts', 0)) > 0 else PositionSide.SHORT

        return Position(
            symbol=pos_data['symbol'],
            side=side,
            size=Decimal(str(abs(float(pos_data.get('contracts', 0))))),
            entry_price=Decimal(str(pos_data.get('entryPrice', 0))),
            mark_price=Decimal(str(pos_data.get('markPrice', 0))) if pos_data.get('markPrice') else None,
            liquidation_price=Decimal(str(pos_data.get('liquidationPrice', 0))) if pos_data.get('liquidationPrice') else None,
            unrealized_pnl=Decimal(str(pos_data.get('unrealizedPnl', 0))),
            leverage=int(pos_data.get('leverage', 1)),
            margin=Decimal(str(pos_data.get('collateral', 0))) if pos_data.get('collateral') else None,
            raw_data=pos_data
        )

    def _parse_trade(self, trade_data: Dict[str, Any]) -> Trade:
        """Parse CCXT trade data into Trade object."""
        return Trade(
            trade_id=str(trade_data['id']),
            order_id=str(trade_data.get('order', '')),
            symbol=trade_data['symbol'],
            side=OrderSide(trade_data['side']),
            price=Decimal(str(trade_data['price'])),
            quantity=Decimal(str(trade_data['amount'])),
            fee=Decimal(str(trade_data['fee']['cost'])) if trade_data.get('fee') else None,
            fee_asset=trade_data['fee']['currency'] if trade_data.get('fee') else None,
            timestamp=datetime.fromtimestamp(trade_data['timestamp'] / 1000) if trade_data.get('timestamp') else None,
            is_maker=trade_data.get('maker', False)
        )

    # ========================================================================
    # Properties
    # ========================================================================

    @property
    def name(self) -> str:
        """Get exchange name."""
        return f"binance_{self.market_type}"

    @property
    def supports_futures(self) -> bool:
        """Check if futures trading is supported."""
        return self.market_type == "futures"
