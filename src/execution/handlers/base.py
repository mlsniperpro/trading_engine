"""
Base execution handler for chain of responsibility pattern.

This module defines the abstract base class for execution handlers.
Each handler can process a request or pass it to the next handler.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from src.core.events import TradingSignalGenerated, OrderSide, OrderType


class ExecutionResultStatus(str, Enum):
    """Execution result status."""
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    SKIP = "skip"


@dataclass
class ExecutionContext:
    """
    Context object passed through the execution chain.

    Contains all information needed for order execution and is
    mutated by each handler in the chain.
    """
    # Original signal
    signal: TradingSignalGenerated

    # Order parameters (set by handlers)
    quantity: Optional[float] = None
    price: Optional[float] = None
    order_type: OrderType = OrderType.LIMIT

    # Risk parameters (calculated by risk handler)
    position_size_usd: Optional[float] = None
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None

    # Execution result (set by executor handler)
    order_id: Optional[str] = None
    exchange_order_id: Optional[str] = None
    filled_quantity: Optional[float] = None
    avg_fill_price: Optional[float] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Handler execution log
    handler_log: List[Dict[str, Any]] = field(default_factory=list)

    def log_handler(self, handler_name: str, status: str, message: str, **kwargs):
        """Log handler execution."""
        self.handler_log.append({
            "handler": handler_name,
            "status": status,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        })


@dataclass
class ExecutionResult:
    """
    Result from an execution handler.

    Indicates whether execution should continue, stop, or retry.
    """
    status: ExecutionResultStatus
    message: str
    context: ExecutionContext
    error: Optional[Exception] = None
    retry_after_seconds: Optional[float] = None

    @property
    def is_success(self) -> bool:
        """Check if execution was successful."""
        return self.status == ExecutionResultStatus.SUCCESS

    @property
    def is_failure(self) -> bool:
        """Check if execution failed."""
        return self.status == ExecutionResultStatus.FAILURE

    @property
    def should_retry(self) -> bool:
        """Check if execution should be retried."""
        return self.status == ExecutionResultStatus.RETRY

    @property
    def should_skip(self) -> bool:
        """Check if this handler should be skipped."""
        return self.status == ExecutionResultStatus.SKIP


class ExecutionHandler(ABC):
    """
    Abstract base class for execution handlers.

    Implements the chain of responsibility pattern for processing
    trade execution requests. Each handler can:
    1. Process the request and pass to next handler (SUCCESS)
    2. Stop execution with failure (FAILURE)
    3. Request a retry (RETRY)
    4. Skip to next handler (SKIP)
    """

    def __init__(self, next_handler: Optional['ExecutionHandler'] = None):
        """
        Initialize handler.

        Args:
            next_handler: Next handler in the chain
        """
        self._next_handler = next_handler

    def set_next(self, handler: 'ExecutionHandler') -> 'ExecutionHandler':
        """
        Set the next handler in the chain.

        Args:
            handler: Next handler

        Returns:
            The handler that was set (for chaining)
        """
        self._next_handler = handler
        return handler

    async def handle(self, context: ExecutionContext) -> ExecutionResult:
        """
        Handle the execution request.

        This is the main entry point that orchestrates the chain.
        Subclasses should override _process() instead.

        Args:
            context: Execution context

        Returns:
            Execution result
        """
        try:
            # Process current handler
            result = await self._process(context)

            # Log execution
            context.log_handler(
                handler_name=self.__class__.__name__,
                status=result.status.value,
                message=result.message
            )

            # If successful and there's a next handler, continue chain
            if result.is_success and self._next_handler:
                return await self._next_handler.handle(context)

            # Otherwise return result (success without next, failure, or retry)
            return result

        except Exception as e:
            # Log error
            context.log_handler(
                handler_name=self.__class__.__name__,
                status="error",
                message=f"Handler raised exception: {str(e)}",
                error_type=type(e).__name__
            )

            # Return failure result
            return ExecutionResult(
                status=ExecutionResultStatus.FAILURE,
                message=f"Handler {self.__class__.__name__} failed: {str(e)}",
                context=context,
                error=e
            )

    @abstractmethod
    async def _process(self, context: ExecutionContext) -> ExecutionResult:
        """
        Process the execution request.

        Subclasses must implement this method to define their specific logic.

        Args:
            context: Execution context

        Returns:
            Execution result
        """
        pass

    def __repr__(self) -> str:
        """String representation."""
        next_name = self._next_handler.__class__.__name__ if self._next_handler else "None"
        return f"{self.__class__.__name__}(next={next_name})"
