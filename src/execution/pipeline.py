"""
Execution pipeline orchestrating the chain of responsibility.

Coordinates the execution handlers in sequence:
Validator → Risk Manager → Executor → Reconciler
"""

import logging
from typing import Optional, Callable

from src.execution.handlers.base import (
    ExecutionHandler,
    ExecutionContext,
    ExecutionResult,
    ExecutionResultStatus
)
from src.execution.handlers.validator import ValidationHandler
from src.execution.handlers.risk_manager import RiskManagementHandler
from src.execution.handlers.executor import OrderExecutorHandler
from src.execution.handlers.reconciler import ReconciliationHandler
from src.core.events import TradingSignalGenerated

logger = logging.getLogger(__name__)


class ExecutionPipeline:
    """
    Execution pipeline implementing chain of responsibility.

    The pipeline executes handlers in order:
    1. ValidationHandler - Validates signal parameters
    2. RiskManagementHandler - Calculates position size and risk
    3. OrderExecutorHandler - Executes order on exchange
    4. ReconciliationHandler - Verifies order fill

    Each handler can:
    - Pass to next handler (SUCCESS)
    - Stop with failure (FAILURE)
    - Request retry (RETRY)
    """

    def __init__(
        self,
        validator: Optional[ValidationHandler] = None,
        risk_manager: Optional[RiskManagementHandler] = None,
        executor: Optional[OrderExecutorHandler] = None,
        reconciler: Optional[ReconciliationHandler] = None,
    ):
        """
        Initialize execution pipeline.

        Args:
            validator: Validation handler
            risk_manager: Risk management handler
            executor: Order executor handler
            reconciler: Reconciliation handler
        """
        # Create default handlers if not provided
        self.validator = validator or ValidationHandler()
        self.risk_manager = risk_manager or RiskManagementHandler()
        self.executor = executor or OrderExecutorHandler()
        self.reconciler = reconciler or ReconciliationHandler()

        # Build the chain
        self._build_chain()

    def _build_chain(self):
        """Build the handler chain."""
        # Chain: Validator → Risk → Executor → Reconciler
        self.validator.set_next(self.risk_manager)
        self.risk_manager.set_next(self.executor)
        self.executor.set_next(self.reconciler)

        logger.info(
            f"Execution pipeline built: "
            f"{self.validator.__class__.__name__} -> "
            f"{self.risk_manager.__class__.__name__} -> "
            f"{self.executor.__class__.__name__} -> "
            f"{self.reconciler.__class__.__name__}"
        )

    async def execute(self, signal: TradingSignalGenerated) -> ExecutionResult:
        """
        Execute the pipeline for a trading signal.

        Args:
            signal: Trading signal to execute

        Returns:
            Execution result
        """
        logger.info(
            f"Starting execution pipeline for signal: "
            f"{signal.symbol} {signal.side.value} "
            f"(strength={signal.signal_strength}, confluence={signal.confluence_score})"
        )

        # Create execution context
        context = ExecutionContext(signal=signal)

        # Execute the chain starting from validator
        result = await self.validator.handle(context)

        # Log final result
        self._log_result(result)

        return result

    def _log_result(self, result: ExecutionResult):
        """
        Log execution result.

        Args:
            result: Execution result
        """
        context = result.context
        signal = context.signal

        if result.is_success:
            logger.info(
                f"Execution pipeline SUCCESS: {signal.symbol} {signal.side.value} "
                f"order_id={context.order_id}, "
                f"filled={context.filled_quantity} @ {context.avg_fill_price}"
            )
            logger.debug(f"Handler log: {context.handler_log}")
        elif result.is_failure:
            logger.error(
                f"Execution pipeline FAILED: {signal.symbol} {signal.side.value} "
                f"reason={result.message}"
            )
            logger.debug(f"Handler log: {context.handler_log}")
        elif result.should_retry:
            logger.warning(
                f"Execution pipeline RETRY requested: {signal.symbol} {signal.side.value} "
                f"retry_after={result.retry_after_seconds}s"
            )

    def set_balance_provider(self, provider: Callable):
        """
        Set account balance provider for risk manager.

        Args:
            provider: Async function that returns account balance
        """
        self.risk_manager.set_account_balance_provider(provider)

    def set_positions_provider(self, provider: Callable):
        """
        Set positions provider for risk manager.

        Args:
            provider: Async function that returns current positions
        """
        self.risk_manager.set_positions_provider(provider)

    def get_handler_chain(self) -> str:
        """
        Get handler chain as string.

        Returns:
            Handler chain representation
        """
        return (
            f"{self.validator.__class__.__name__} -> "
            f"{self.risk_manager.__class__.__name__} -> "
            f"{self.executor.__class__.__name__} -> "
            f"{self.reconciler.__class__.__name__}"
        )
