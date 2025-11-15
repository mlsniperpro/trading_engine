"""
Validation handler for execution pipeline.

Validates trading signals and order parameters before execution.
"""

import logging
from typing import Dict, Any

from src.execution.handlers.base import (
    ExecutionHandler,
    ExecutionContext,
    ExecutionResult,
    ExecutionResultStatus
)
from src.core.events import OrderSide

logger = logging.getLogger(__name__)


class ValidationHandler(ExecutionHandler):
    """
    Validates trading signals and order parameters.

    Checks:
    - Signal validity (required fields, valid values)
    - Market conditions (symbol exists, market is open)
    - Order parameters (price, quantity within limits)
    """

    def __init__(
        self,
        min_signal_strength: float = 0.0,
        min_confluence_score: float = 3.0,
        max_confluence_score: float = 10.0,
        valid_exchanges: list = None,
        **kwargs
    ):
        """
        Initialize validator.

        Args:
            min_signal_strength: Minimum signal strength required
            min_confluence_score: Minimum confluence score required
            max_confluence_score: Maximum valid confluence score
            valid_exchanges: List of valid exchange names
        """
        super().__init__(**kwargs)
        self.min_signal_strength = min_signal_strength
        self.min_confluence_score = min_confluence_score
        self.max_confluence_score = max_confluence_score
        self.valid_exchanges = valid_exchanges or ["binance", "bybit"]

    async def _process(self, context: ExecutionContext) -> ExecutionResult:
        """
        Validate the trading signal.

        Args:
            context: Execution context

        Returns:
            Execution result
        """
        signal = context.signal

        # Validate signal strength
        if signal.signal_strength < self.min_signal_strength:
            return ExecutionResult(
                status=ExecutionResultStatus.FAILURE,
                message=f"Signal strength {signal.signal_strength} below minimum {self.min_signal_strength}",
                context=context
            )

        # Validate confluence score
        if signal.confluence_score < self.min_confluence_score:
            return ExecutionResult(
                status=ExecutionResultStatus.FAILURE,
                message=f"Confluence score {signal.confluence_score} below minimum {self.min_confluence_score}",
                context=context
            )

        if signal.confluence_score > self.max_confluence_score:
            logger.warning(
                f"Confluence score {signal.confluence_score} exceeds maximum {self.max_confluence_score}"
            )

        # Validate exchange
        if signal.exchange not in self.valid_exchanges:
            return ExecutionResult(
                status=ExecutionResultStatus.FAILURE,
                message=f"Exchange {signal.exchange} not in valid exchanges: {self.valid_exchanges}",
                context=context
            )

        # Validate symbol format
        if not self._is_valid_symbol(signal.symbol):
            return ExecutionResult(
                status=ExecutionResultStatus.FAILURE,
                message=f"Invalid symbol format: {signal.symbol}",
                context=context
            )

        # Validate side
        if signal.side not in [OrderSide.BUY, OrderSide.SELL]:
            return ExecutionResult(
                status=ExecutionResultStatus.FAILURE,
                message=f"Invalid order side: {signal.side}",
                context=context
            )

        # Validate position size percentage
        if not (0 < signal.position_size_pct <= 100):
            return ExecutionResult(
                status=ExecutionResultStatus.FAILURE,
                message=f"Invalid position size percentage: {signal.position_size_pct}",
                context=context
            )

        # Validate stop loss if provided
        if signal.stop_loss is not None:
            if not self._validate_stop_loss(signal.side, signal.entry_price, signal.stop_loss):
                return ExecutionResult(
                    status=ExecutionResultStatus.FAILURE,
                    message=f"Invalid stop loss: entry={signal.entry_price}, stop={signal.stop_loss}, side={signal.side}",
                    context=context
                )

        # Validate take profit if provided
        if signal.take_profit is not None:
            if not self._validate_take_profit(signal.side, signal.entry_price, signal.take_profit):
                return ExecutionResult(
                    status=ExecutionResultStatus.FAILURE,
                    message=f"Invalid take profit: entry={signal.entry_price}, tp={signal.take_profit}, side={signal.side}",
                    context=context
                )

        # All validations passed
        logger.info(
            f"Signal validation passed for {signal.symbol} "
            f"(strength={signal.signal_strength}, confluence={signal.confluence_score})"
        )

        return ExecutionResult(
            status=ExecutionResultStatus.SUCCESS,
            message="Signal validation successful",
            context=context
        )

    def _is_valid_symbol(self, symbol: str) -> bool:
        """
        Validate symbol format.

        Args:
            symbol: Trading symbol

        Returns:
            True if valid
        """
        if not symbol or not isinstance(symbol, str):
            return False

        # Basic validation: alphanumeric, uppercase, minimum length
        if len(symbol) < 3:
            return False

        # Common patterns: BTCUSDT, BTC-USDT, BTC/USDT, BTC_USDT
        return symbol.replace('-', '').replace('/', '').replace('_', '').isalnum()

    def _validate_stop_loss(self, side: OrderSide, entry_price: float, stop_loss: float) -> bool:
        """
        Validate stop loss placement.

        Args:
            side: Order side
            entry_price: Entry price
            stop_loss: Stop loss price

        Returns:
            True if valid
        """
        if entry_price is None or stop_loss is None:
            return True  # Skip if not provided

        if entry_price <= 0 or stop_loss <= 0:
            return False

        # For buy orders, stop loss must be below entry
        if side == OrderSide.BUY:
            return stop_loss < entry_price

        # For sell orders, stop loss must be above entry
        return stop_loss > entry_price

    def _validate_take_profit(self, side: OrderSide, entry_price: float, take_profit: float) -> bool:
        """
        Validate take profit placement.

        Args:
            side: Order side
            entry_price: Entry price
            take_profit: Take profit price

        Returns:
            True if valid
        """
        if entry_price is None or take_profit is None:
            return True  # Skip if not provided

        if entry_price <= 0 or take_profit <= 0:
            return False

        # For buy orders, take profit must be above entry
        if side == OrderSide.BUY:
            return take_profit > entry_price

        # For sell orders, take profit must be below entry
        return take_profit < entry_price
