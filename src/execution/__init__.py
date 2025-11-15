"""
Execution engine module.

Provides order execution infrastructure with:
- Chain of responsibility pattern for execution handlers
- Exchange adapters (CCXT-based)
- Order lifecycle management
- Event-driven execution
"""

from src.execution.engine import ExecutionEngine
from src.execution.pipeline import ExecutionPipeline
from src.execution.order_manager import OrderManager, ManagedOrder, OrderState

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
from src.execution.exchanges.binance_ccxt import BinanceCCXTAdapter
from src.execution.exchanges.exchange_factory import ExchangeFactory, get_exchange_factory

__all__ = [
    # Engine
    'ExecutionEngine',
    'ExecutionPipeline',
    'OrderManager',
    'ManagedOrder',
    'OrderState',

    # Handlers
    'ExecutionHandler',
    'ExecutionContext',
    'ExecutionResult',
    'ExecutionResultStatus',
    'ValidationHandler',
    'RiskManagementHandler',
    'OrderExecutorHandler',
    'ReconciliationHandler',

    # Exchanges
    'ExchangeAdapter',
    'Balance',
    'Position',
    'OrderInfo',
    'ExchangeError',
    'RateLimitError',
    'InsufficientBalanceError',
    'OrderNotFoundError',
    'InvalidOrderError',
    'BinanceCCXTAdapter',
    'ExchangeFactory',
    'get_exchange_factory',
]
