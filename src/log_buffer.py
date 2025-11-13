"""
In-memory log buffer for API access.
Stores recent logs that can be accessed via HTTP endpoints.
"""

import logging
from collections import deque
from datetime import datetime
from typing import List, Dict
import threading


class LogBuffer(logging.Handler):
    """
    Custom logging handler that stores logs in memory.
    Thread-safe circular buffer for recent log entries.
    """

    def __init__(self, max_size=1000):
        super().__init__()
        self.max_size = max_size
        self.buffer = deque(maxlen=max_size)
        self.lock = threading.RLock()  # Use RLock instead of Lock to prevent deadlock
        self.error_count = 0
        self.warning_count = 0
        self.info_count = 0

    def emit(self, record):
        """Store log record in buffer."""
        try:
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno
            }

            with self.lock:
                self.buffer.append(log_entry)

                # Update counters
                if record.levelname == "ERROR":
                    self.error_count += 1
                elif record.levelname == "WARNING":
                    self.warning_count += 1
                elif record.levelname == "INFO":
                    self.info_count += 1

        except Exception:
            self.handleError(record)

    def get_logs(
        self,
        lines: int = 100,
        level: str = None,
        search: str = None
    ) -> List[Dict]:
        """
        Get logs from buffer with optional filtering.

        Args:
            lines: Maximum number of logs to return
            level: Filter by log level (ERROR, WARNING, INFO, DEBUG)
            search: Search term to filter messages

        Returns:
            List of log entries (newest first)
        """
        with self.lock:
            logs = list(self.buffer)

        # Filter by level
        if level:
            logs = [log for log in logs if log["level"] == level.upper()]

        # Filter by search term
        if search:
            logs = [
                log for log in logs
                if search.lower() in log["message"].lower()
            ]

        # Return most recent logs first
        logs.reverse()

        # Limit number of logs
        return logs[:lines]

    def get_stats(self) -> Dict:
        """Get log statistics."""
        with self.lock:
            return {
                "total_logs": len(self.buffer),
                "max_size": self.max_size,
                "errors": self.error_count,
                "warnings": self.warning_count,
                "info": self.info_count,
                "buffer_full": len(self.buffer) >= self.max_size
            }

    def clear(self):
        """Clear the log buffer."""
        with self.lock:
            self.buffer.clear()
            self.error_count = 0
            self.warning_count = 0
            self.info_count = 0


# Global log buffer instance
log_buffer = LogBuffer(max_size=1000)


def setup_log_buffer():
    """Add log buffer handler to root logger."""
    # Get root logger
    root_logger = logging.getLogger()

    # Add buffer handler if not already added
    if not any(isinstance(h, LogBuffer) for h in root_logger.handlers):
        # Set format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        log_buffer.setFormatter(formatter)

        # Add to root logger
        root_logger.addHandler(log_buffer)

    return log_buffer
