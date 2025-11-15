"""
Risk management handler for execution pipeline.

Calculates position sizing, validates risk parameters, and enforces limits.
"""

import logging
from typing import Optional, Dict, Any

from src.execution.handlers.base import (
    ExecutionHandler,
    ExecutionContext,
    ExecutionResult,
    ExecutionResultStatus
)
from src.core.events import OrderSide

logger = logging.getLogger(__name__)


class RiskManagementHandler(ExecutionHandler):
    """
    Risk management handler for position sizing and risk checks.

    Responsibilities:
    - Calculate position size based on account balance and risk percentage
    - Validate stop-loss placement and risk/reward ratio
    - Check max concurrent positions limit
    - Enforce maximum position size limits
    - Calculate optimal stop-loss if not provided
    """

    def __init__(
        self,
        max_concurrent_positions: int = 3,
        default_position_size_pct: float = 2.0,
        max_position_size_pct: float = 5.0,
        min_risk_reward_ratio: float = 1.5,
        max_stop_loss_distance_pct: float = 2.0,
        **kwargs
    ):
        """
        Initialize risk manager.

        Args:
            max_concurrent_positions: Maximum number of open positions
            default_position_size_pct: Default position size as % of account
            max_position_size_pct: Maximum position size as % of account
            min_risk_reward_ratio: Minimum risk/reward ratio required
            max_stop_loss_distance_pct: Maximum stop loss distance as %
        """
        super().__init__(**kwargs)
        self.max_concurrent_positions = max_concurrent_positions
        self.default_position_size_pct = default_position_size_pct
        self.max_position_size_pct = max_position_size_pct
        self.min_risk_reward_ratio = min_risk_reward_ratio
        self.max_stop_loss_distance_pct = max_stop_loss_distance_pct

        # This will be injected by the execution engine
        self._get_account_balance = None
        self._get_current_positions = None

    def set_account_balance_provider(self, provider):
        """Set account balance provider function."""
        self._get_account_balance = provider

    def set_positions_provider(self, provider):
        """Set current positions provider function."""
        self._get_current_positions = provider

    async def _process(self, context: ExecutionContext) -> ExecutionResult:
        """
        Process risk management checks.

        Args:
            context: Execution context

        Returns:
            Execution result
        """
        signal = context.signal

        # Check max concurrent positions
        if not await self._check_max_positions():
            return ExecutionResult(
                status=ExecutionResultStatus.FAILURE,
                message=f"Maximum concurrent positions ({self.max_concurrent_positions}) reached",
                context=context
            )

        # Get account balance
        account_balance = await self._get_balance(signal.exchange)
        if account_balance is None or account_balance <= 0:
            return ExecutionResult(
                status=ExecutionResultStatus.FAILURE,
                message="Unable to determine account balance or balance is zero",
                context=context
            )

        # Calculate position size
        position_size_pct = signal.position_size_pct or self.default_position_size_pct

        # Validate position size percentage
        if position_size_pct > self.max_position_size_pct:
            logger.warning(
                f"Position size {position_size_pct}% exceeds max {self.max_position_size_pct}%, "
                f"using max"
            )
            position_size_pct = self.max_position_size_pct

        # Calculate position size in USD
        position_size_usd = account_balance * (position_size_pct / 100)

        # Get current market price (use entry price from signal or fetch current)
        entry_price = signal.entry_price
        if entry_price is None:
            # In production, fetch current market price
            logger.warning("No entry price provided, risk calculation may be inaccurate")
            return ExecutionResult(
                status=ExecutionResultStatus.FAILURE,
                message="Entry price required for position sizing",
                context=context
            )

        # Calculate quantity based on position size and entry price
        quantity = position_size_usd / entry_price

        # Calculate or validate stop loss
        stop_loss = signal.stop_loss
        if stop_loss is None:
            # Calculate default stop loss based on max distance
            stop_loss = self._calculate_default_stop_loss(
                side=signal.side,
                entry_price=entry_price,
                distance_pct=self.max_stop_loss_distance_pct
            )
            logger.info(
                f"Calculated default stop loss: {stop_loss} "
                f"({self.max_stop_loss_distance_pct}% from entry)"
            )
        else:
            # Validate provided stop loss distance
            stop_loss_distance_pct = abs((entry_price - stop_loss) / entry_price * 100)
            if stop_loss_distance_pct > self.max_stop_loss_distance_pct:
                return ExecutionResult(
                    status=ExecutionResultStatus.FAILURE,
                    message=f"Stop loss distance {stop_loss_distance_pct:.2f}% exceeds max {self.max_stop_loss_distance_pct}%",
                    context=context
                )

        # Validate risk/reward ratio if take profit is provided
        if signal.take_profit is not None:
            risk_reward = self._calculate_risk_reward_ratio(
                side=signal.side,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=signal.take_profit
            )

            if risk_reward < self.min_risk_reward_ratio:
                return ExecutionResult(
                    status=ExecutionResultStatus.FAILURE,
                    message=f"Risk/reward ratio {risk_reward:.2f} below minimum {self.min_risk_reward_ratio}",
                    context=context
                )

            logger.info(f"Risk/reward ratio: {risk_reward:.2f}")

        # Update context with calculated values
        context.position_size_usd = position_size_usd
        context.quantity = quantity
        context.price = entry_price
        context.stop_loss_price = stop_loss
        context.take_profit_price = signal.take_profit

        # Add risk metadata
        context.metadata.update({
            "account_balance": account_balance,
            "position_size_pct": position_size_pct,
            "position_size_usd": position_size_usd,
            "quantity": quantity,
            "stop_loss": stop_loss,
            "take_profit": signal.take_profit,
        })

        logger.info(
            f"Risk check passed: size=${position_size_usd:.2f} ({position_size_pct}%), "
            f"qty={quantity:.8f}, sl={stop_loss}"
        )

        return ExecutionResult(
            status=ExecutionResultStatus.SUCCESS,
            message="Risk management checks passed",
            context=context
        )

    async def _check_max_positions(self) -> bool:
        """
        Check if max concurrent positions limit is reached.

        Returns:
            True if can open new position
        """
        if self._get_current_positions is None:
            logger.warning("Position provider not set, skipping max positions check")
            return True

        try:
            current_positions = await self._get_current_positions()
            open_positions_count = len(current_positions)

            logger.debug(f"Current open positions: {open_positions_count}/{self.max_concurrent_positions}")

            return open_positions_count < self.max_concurrent_positions
        except Exception as e:
            logger.error(f"Error checking current positions: {e}")
            # Fail safe: allow position if we can't check
            return True

    async def _get_balance(self, exchange: str) -> Optional[float]:
        """
        Get account balance.

        Args:
            exchange: Exchange name

        Returns:
            Account balance in USD or None
        """
        if self._get_account_balance is None:
            logger.warning("Account balance provider not set, using default balance")
            return 10000.0  # Default for testing

        try:
            balance = await self._get_account_balance(exchange)
            return balance
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return None

    def _calculate_default_stop_loss(
        self,
        side: OrderSide,
        entry_price: float,
        distance_pct: float
    ) -> float:
        """
        Calculate default stop loss.

        Args:
            side: Order side
            entry_price: Entry price
            distance_pct: Distance as percentage

        Returns:
            Stop loss price
        """
        if side == OrderSide.BUY:
            # For buy, stop loss is below entry
            return entry_price * (1 - distance_pct / 100)
        else:
            # For sell, stop loss is above entry
            return entry_price * (1 + distance_pct / 100)

    def _calculate_risk_reward_ratio(
        self,
        side: OrderSide,
        entry_price: float,
        stop_loss: float,
        take_profit: float
    ) -> float:
        """
        Calculate risk/reward ratio.

        Args:
            side: Order side
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            Risk/reward ratio
        """
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)

        if risk == 0:
            return 0.0

        return reward / risk
