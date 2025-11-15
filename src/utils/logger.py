"""
Enhanced Logging Utilities

Provides structured logging with:
- JSON formatting for production
- Performance metrics
- Context correlation
- Multi-level filtering
"""

import logging
import json
import sys
import time
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path
import threading
from contextlib import contextmanager


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'correlation_id'):
            log_entry['correlation_id'] = record.correlation_id
        if hasattr(record, 'pair'):
            log_entry['pair'] = record.pair
        if hasattr(record, 'exchange'):
            log_entry['exchange'] = record.exchange
        if hasattr(record, 'strategy'):
            log_entry['strategy'] = record.strategy
        if hasattr(record, 'execution_time'):
            log_entry['execution_time'] = record.execution_time
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)


class PerformanceLogger:
    """Logger for tracking performance metrics."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._start_times = {}
        self._lock = threading.Lock()
    
    @contextmanager
    def timer(self, operation: str, **context):
        """Context manager for timing operations."""
        start_time = time.time()
        operation_id = f"{operation}_{threading.get_ident()}_{start_time}"
        
        try:
            with self._lock:
                self._start_times[operation_id] = start_time
            yield
        finally:
            end_time = time.time()
            execution_time = end_time - start_time
            
            with self._lock:
                self._start_times.pop(operation_id, None)
            
            extra = {'execution_time': execution_time, **context}
            self.logger.info(f"Operation completed: {operation}", extra=extra)
    
    def log_metric(self, metric_name: str, value: float, **context):
        """Log a performance metric."""
        extra = {'metric_name': metric_name, 'metric_value': value, **context}
        self.logger.info(f"Metric: {metric_name}={value}", extra=extra)


class TradingLogger:
    """Specialized logger for trading operations."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.performance = PerformanceLogger(self.logger)
    
    def trade_signal(self, pair: str, signal: str, confidence: float, **context):
        """Log trading signal."""
        extra = {
            'pair': pair,
            'signal': signal,
            'confidence': confidence,
            **context
        }
        self.logger.info(f"Signal: {signal} for {pair} (confidence={confidence})", extra=extra)
    
    def order_event(self, order_id: str, event: str, pair: str, **context):
        """Log order events."""
        extra = {
            'order_id': order_id,
            'order_event': event,
            'pair': pair,
            **context
        }
        self.logger.info(f"Order {event}: {order_id} ({pair})", extra=extra)
    
    def position_event(self, pair: str, event: str, size: float, price: float, **context):
        """Log position events."""
        extra = {
            'pair': pair,
            'position_event': event,
            'size': size,
            'price': price,
            **context
        }
        self.logger.info(f"Position {event}: {pair} size={size} @ {price}", extra=extra)
    
    def risk_alert(self, alert_type: str, severity: str, message: str, **context):
        """Log risk management alerts."""
        extra = {
            'alert_type': alert_type,
            'severity': severity,
            **context
        }
        if severity.lower() in ['high', 'critical']:
            self.logger.error(f"Risk Alert [{alert_type}]: {message}", extra=extra)
        else:
            self.logger.warning(f"Risk Alert [{alert_type}]: {message}", extra=extra)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    json_format: bool = True,
    correlation_id: Optional[str] = None
) -> logging.Logger:
    """
    Setup enhanced logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
        json_format: Use JSON formatting
        correlation_id: Optional correlation ID for request tracking
        
    Returns:
        Configured logger instance
    """
    # Create root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Choose formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Add correlation ID to all log records if provided
    if correlation_id:
        old_factory = logging.getLogRecordFactory()
        
        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.correlation_id = correlation_id
            return record
        
        logging.setLogRecordFactory(record_factory)
    
    return logger


def get_trading_logger(name: str) -> TradingLogger:
    """Get a trading-specific logger instance."""
    return TradingLogger(name)


def get_performance_logger(name: str) -> PerformanceLogger:
    """Get a performance logger instance."""
    logger = logging.getLogger(name)
    return PerformanceLogger(logger)


# Module-level convenience functions
def log_trade_execution(
    pair: str,
    side: str,
    size: float,
    price: float,
    execution_time: float,
    exchange: str = None,
    order_id: str = None
):
    """Log trade execution details."""
    logger = get_trading_logger("trading.execution")
    
    context = {
        'side': side,
        'size': size,
        'price': price,
        'execution_time': execution_time
    }
    
    if exchange:
        context['exchange'] = exchange
    if order_id:
        context['order_id'] = order_id
    
    logger.trade_signal(pair, f"EXECUTED_{side.upper()}", 1.0, **context)


def log_analytics_calculation(
    module: str,
    calculation: str,
    execution_time: float,
    pair: str = None,
    **metrics
):
    """Log analytics calculation performance."""
    logger = get_performance_logger(f"analytics.{module}")
    
    context = {
        'calculation': calculation,
        'execution_time': execution_time
    }
    
    if pair:
        context['pair'] = pair
    
    context.update(metrics)
    
    logger.log_metric(f"{module}.{calculation}", execution_time, **context)