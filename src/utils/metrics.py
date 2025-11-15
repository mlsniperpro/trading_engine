"""
Performance Metrics Collection

Provides comprehensive metrics for:
- Trading performance tracking
- System performance monitoring
- Real-time statistics
- Alert generation
"""

import time
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import statistics
import logging

logger = logging.getLogger(__name__)


@dataclass
class MetricValue:
    """Individual metric data point."""
    timestamp: datetime
    value: float
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSummary:
    """Statistical summary of metric values."""
    count: int
    sum: float
    min: float
    max: float
    mean: float
    median: float
    std_dev: float
    p95: float
    p99: float


class MetricsCollector:
    """Thread-safe metrics collection system."""
    
    def __init__(self, max_history: int = 10000, cleanup_interval: int = 3600):
        """
        Initialize metrics collector.
        
        Args:
            max_history: Maximum number of data points per metric
            cleanup_interval: Cleanup interval in seconds
        """
        self._metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._timers: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.RLock()
        self._max_history = max_history
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()
        
        logger.info(f"MetricsCollector initialized (max_history={max_history})")
    
    def increment(self, metric_name: str, value: float = 1.0, tags: Dict[str, str] = None):
        """Increment a counter metric."""
        with self._lock:
            full_name = self._build_metric_name(metric_name, tags)
            self._counters[full_name] += value
            self._add_metric_point(metric_name, value, tags)
    
    def gauge(self, metric_name: str, value: float, tags: Dict[str, str] = None):
        """Set a gauge metric value."""
        with self._lock:
            full_name = self._build_metric_name(metric_name, tags)
            self._gauges[full_name] = value
            self._add_metric_point(metric_name, value, tags)
    
    def timer(self, metric_name: str, duration: float, tags: Dict[str, str] = None):
        """Record a timing metric."""
        with self._lock:
            full_name = self._build_metric_name(metric_name, tags)
            self._timers[full_name].append(duration)
            self._add_metric_point(metric_name, duration, tags)
    
    def histogram(self, metric_name: str, value: float, tags: Dict[str, str] = None):
        """Record a histogram metric (alias for timer)."""
        self.timer(metric_name, value, tags)
    
    def _add_metric_point(self, metric_name: str, value: float, tags: Dict[str, str] = None):
        """Add metric data point to history."""
        metric_point = MetricValue(
            timestamp=datetime.now(),
            value=value,
            tags=tags or {}
        )
        self._metrics[metric_name].append(metric_point)
        
        # Cleanup old data if needed
        if time.time() - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_data()
    
    def _build_metric_name(self, metric_name: str, tags: Dict[str, str] = None) -> str:
        """Build full metric name with tags."""
        if not tags:
            return metric_name
        
        tag_string = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{metric_name}[{tag_string}]"
    
    def get_summary(self, metric_name: str, time_window: timedelta = None) -> Optional[MetricSummary]:
        """Get statistical summary of a metric."""
        with self._lock:
            if metric_name not in self._metrics:
                return None
            
            points = list(self._metrics[metric_name])
            
            # Filter by time window if specified
            if time_window:
                cutoff = datetime.now() - time_window
                points = [p for p in points if p.timestamp >= cutoff]
            
            if not points:
                return None
            
            values = [p.value for p in points]
            
            try:
                return MetricSummary(
                    count=len(values),
                    sum=sum(values),
                    min=min(values),
                    max=max(values),
                    mean=statistics.mean(values),
                    median=statistics.median(values),
                    std_dev=statistics.stdev(values) if len(values) > 1 else 0.0,
                    p95=self._percentile(values, 0.95),
                    p99=self._percentile(values, 0.99)
                )
            except Exception as e:
                logger.error(f"Error calculating metric summary: {e}")
                return None
    
    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile value."""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        k = (len(sorted_values) - 1) * percentile
        f = int(k)
        c = k - f
        
        if f + 1 < len(sorted_values):
            return sorted_values[f] + c * (sorted_values[f + 1] - sorted_values[f])
        else:
            return sorted_values[f]
    
    def get_current_values(self) -> Dict[str, Any]:
        """Get current values of all metrics."""
        with self._lock:
            return {
                'counters': dict(self._counters),
                'gauges': dict(self._gauges),
                'timers': {k: v[-10:] for k, v in self._timers.items()}  # Last 10 values
            }
    
    def _cleanup_old_data(self):
        """Clean up old metric data."""
        cutoff = datetime.now() - timedelta(hours=24)  # Keep last 24 hours
        
        for metric_name in list(self._metrics.keys()):
            points = self._metrics[metric_name]
            # Remove old points
            while points and points[0].timestamp < cutoff:
                points.popleft()
        
        self._last_cleanup = time.time()
        logger.debug("Metrics cleanup completed")


class TradingMetrics:
    """Trading-specific metrics collection."""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    def trade_executed(self, pair: str, side: str, size: float, price: float, execution_time: float):
        """Record trade execution metrics."""
        tags = {'pair': pair, 'side': side}
        
        self.collector.increment('trades.executed', 1.0, tags)
        self.collector.gauge('trades.size', size, tags)
        self.collector.gauge('trades.price', price, tags)
        self.collector.timer('trades.execution_time', execution_time, tags)
    
    def signal_generated(self, pair: str, signal_type: str, confidence: float):
        """Record signal generation metrics."""
        tags = {'pair': pair, 'signal_type': signal_type}
        
        self.collector.increment('signals.generated', 1.0, tags)
        self.collector.gauge('signals.confidence', confidence, tags)
    
    def position_update(self, pair: str, position_size: float, unrealized_pnl: float):
        """Record position metrics."""
        tags = {'pair': pair}
        
        self.collector.gauge('positions.size', abs(position_size), tags)
        self.collector.gauge('positions.unrealized_pnl', unrealized_pnl, tags)
    
    def risk_event(self, event_type: str, severity: str, pair: str = None):
        """Record risk management events."""
        tags = {'event_type': event_type, 'severity': severity}
        if pair:
            tags['pair'] = pair
        
        self.collector.increment('risk.events', 1.0, tags)
    
    def order_book_update(self, pair: str, bid_price: float, ask_price: float, spread: float):
        """Record order book metrics."""
        tags = {'pair': pair}
        
        self.collector.gauge('orderbook.bid_price', bid_price, tags)
        self.collector.gauge('orderbook.ask_price', ask_price, tags)
        self.collector.gauge('orderbook.spread', spread, tags)
        self.collector.gauge('orderbook.spread_bps', (spread / ((bid_price + ask_price) / 2)) * 10000, tags)


class SystemMetrics:
    """System performance metrics collection."""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    def api_call(self, endpoint: str, duration: float, status_code: int):
        """Record API call metrics."""
        tags = {'endpoint': endpoint, 'status': str(status_code)}
        
        self.collector.timer('api.duration', duration, tags)
        self.collector.increment('api.calls', 1.0, tags)
    
    def database_query(self, query_type: str, duration: float, rows_affected: int = 0):
        """Record database query metrics."""
        tags = {'query_type': query_type}
        
        self.collector.timer('db.query_duration', duration, tags)
        self.collector.gauge('db.rows_affected', rows_affected, tags)
        self.collector.increment('db.queries', 1.0, tags)
    
    def memory_usage(self, process: str, memory_mb: float):
        """Record memory usage metrics."""
        tags = {'process': process}
        self.collector.gauge('system.memory_mb', memory_mb, tags)
    
    def cpu_usage(self, process: str, cpu_percent: float):
        """Record CPU usage metrics."""
        tags = {'process': process}
        self.collector.gauge('system.cpu_percent', cpu_percent, tags)
    
    def event_processed(self, event_type: str, processing_time: float):
        """Record event processing metrics."""
        tags = {'event_type': event_type}
        
        self.collector.timer('events.processing_time', processing_time, tags)
        self.collector.increment('events.processed', 1.0, tags)


class MetricsReporter:
    """Metrics reporting and alerting."""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self.alert_thresholds = {}
        self.alert_callbacks = []
    
    def add_alert_threshold(self, metric_name: str, threshold: float, operator: str = 'gt'):
        """Add alert threshold for a metric."""
        self.alert_thresholds[metric_name] = {
            'threshold': threshold,
            'operator': operator
        }
    
    def add_alert_callback(self, callback: Callable[[str, float, float], None]):
        """Add callback for alert notifications."""
        self.alert_callbacks.append(callback)
    
    def check_alerts(self):
        """Check all metrics against alert thresholds."""
        for metric_name, config in self.alert_thresholds.items():
            summary = self.collector.get_summary(metric_name, timedelta(minutes=5))
            
            if summary is None:
                continue
            
            threshold = config['threshold']
            operator = config['operator']
            
            # Check different values based on operator
            values_to_check = {
                'mean': summary.mean,
                'max': summary.max,
                'p95': summary.p95,
                'p99': summary.p99
            }
            
            for value_type, value in values_to_check.items():
                if self._check_threshold(value, threshold, operator):
                    for callback in self.alert_callbacks:
                        try:
                            callback(f"{metric_name}.{value_type}", value, threshold)
                        except Exception as e:
                            logger.error(f"Error in alert callback: {e}")
    
    def _check_threshold(self, value: float, threshold: float, operator: str) -> bool:
        """Check if value crosses threshold."""
        if operator == 'gt':
            return value > threshold
        elif operator == 'lt':
            return value < threshold
        elif operator == 'gte':
            return value >= threshold
        elif operator == 'lte':
            return value <= threshold
        return False
    
    def generate_report(self, time_window: timedelta = None) -> Dict[str, Any]:
        """Generate comprehensive metrics report."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'time_window': str(time_window) if time_window else 'all_time',
            'metrics': {}
        }
        
        # Get summaries for all metrics
        for metric_name in self.collector._metrics.keys():
            summary = self.collector.get_summary(metric_name, time_window)
            if summary:
                report['metrics'][metric_name] = {
                    'count': summary.count,
                    'mean': summary.mean,
                    'median': summary.median,
                    'min': summary.min,
                    'max': summary.max,
                    'std_dev': summary.std_dev,
                    'p95': summary.p95,
                    'p99': summary.p99
                }
        
        return report


# Global metrics collector instance
_metrics_collector = MetricsCollector()
_trading_metrics = TradingMetrics(_metrics_collector)
_system_metrics = SystemMetrics(_metrics_collector)
_metrics_reporter = MetricsReporter(_metrics_collector)


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance."""
    return _metrics_collector


def get_trading_metrics() -> TradingMetrics:
    """Get trading metrics instance."""
    return _trading_metrics


def get_system_metrics() -> SystemMetrics:
    """Get system metrics instance."""
    return _system_metrics


def get_metrics_reporter() -> MetricsReporter:
    """Get metrics reporter instance."""
    return _metrics_reporter