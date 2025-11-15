"""
Time Utilities

Provides time-related utilities for:
- Market session detection
- Timezone handling
- Time window calculations
- Periodic task scheduling
"""

try:
    import pytz
except ImportError:
    print("Warning: pytz not installed. Using UTC timezone only.")
    pytz = None
from datetime import datetime, time, timedelta, timezone
from typing import Tuple, List, Optional, Dict
from enum import Enum
import threading
import time as time_module


class MarketSession(Enum):
    """Market trading sessions."""
    SYDNEY = "SYDNEY"
    TOKYO = "TOKYO"
    LONDON = "LONDON"
    NEW_YORK = "NEW_YORK"
    OVERLAP_ASIA = "OVERLAP_ASIA"
    OVERLAP_LONDON_NY = "OVERLAP_LONDON_NY"
    WEEKEND = "WEEKEND"


class TimeUtils:
    """Core time utilities."""
    
    # Market timezones
    if pytz is not None:
        MARKET_TIMEZONES = {
            'SYDNEY': pytz.timezone('Australia/Sydney'),
            'TOKYO': pytz.timezone('Asia/Tokyo'),
            'LONDON': pytz.timezone('Europe/London'),
            'NEW_YORK': pytz.timezone('America/New_York'),
            'UTC': pytz.UTC
        }
    else:
        # Fallback to UTC when pytz not available
        MARKET_TIMEZONES = {
            'SYDNEY': timezone.utc,
            'TOKYO': timezone.utc,
            'LONDON': timezone.utc,
            'NEW_YORK': timezone.utc,
            'UTC': timezone.utc
        }
    
    # Market session times (in local timezone)
    MARKET_SESSIONS = {
        MarketSession.SYDNEY: (time(17, 0), time(2, 0)),      # 5 PM - 2 AM next day
        MarketSession.TOKYO: (time(0, 0), time(9, 0)),        # Midnight - 9 AM
        MarketSession.LONDON: (time(8, 0), time(17, 0)),      # 8 AM - 5 PM
        MarketSession.NEW_YORK: (time(13, 0), time(22, 0)),   # 1 PM - 10 PM UTC
    }
    
    @staticmethod
    def now_utc() -> datetime:
        """Get current UTC time."""
        return datetime.now(timezone.utc)
    
    @staticmethod
    def to_utc(dt: datetime, source_tz: str = None) -> datetime:
        """Convert datetime to UTC."""
        if dt.tzinfo is None:
            if source_tz:
                tz = TimeUtils.MARKET_TIMEZONES.get(source_tz, timezone.utc)
                if pytz is not None and hasattr(tz, 'localize'):
                    dt = tz.localize(dt)
                else:
                    dt = dt.replace(tzinfo=tz)
            else:
                if pytz is not None:
                    dt = pytz.UTC.localize(dt)
                else:
                    dt = dt.replace(tzinfo=timezone.utc)
        
        if pytz is not None:
            return dt.astimezone(pytz.UTC)
        else:
            return dt.astimezone(timezone.utc)
    
    @staticmethod
    def to_timezone(dt: datetime, target_tz: str) -> datetime:
        """Convert datetime to target timezone."""
        if dt.tzinfo is None:
            if pytz is not None:
                dt = pytz.UTC.localize(dt)
            else:
                dt = dt.replace(tzinfo=timezone.utc)
        
        tz = TimeUtils.MARKET_TIMEZONES.get(target_tz, timezone.utc)
        return dt.astimezone(tz)
    
    @staticmethod
    def unix_timestamp(dt: datetime = None) -> float:
        """Get Unix timestamp."""
        if dt is None:
            dt = TimeUtils.now_utc()
        return dt.timestamp()
    
    @staticmethod
    def from_unix_timestamp(timestamp: float) -> datetime:
        """Create datetime from Unix timestamp."""
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    
    @staticmethod
    def is_weekend(dt: datetime = None) -> bool:
        """Check if datetime is weekend."""
        if dt is None:
            dt = TimeUtils.now_utc()
        return dt.weekday() >= 5  # Saturday=5, Sunday=6
    
    @staticmethod
    def next_weekday(dt: datetime = None) -> datetime:
        """Get next weekday."""
        if dt is None:
            dt = TimeUtils.now_utc()
        
        days_ahead = 7 - dt.weekday()
        if days_ahead == 7:  # Already Monday
            days_ahead = 0
        elif dt.weekday() < 5:  # Already weekday
            return dt
        
        return dt + timedelta(days=days_ahead)
    
    @staticmethod
    def market_open_time(market: str, date: datetime = None) -> datetime:
        """Get market open time for specific date."""
        if date is None:
            date = TimeUtils.now_utc()
        
        if market.upper() not in TimeUtils.MARKET_TIMEZONES:
            raise ValueError(f"Unknown market: {market}")
        
        tz = TimeUtils.MARKET_TIMEZONES[market.upper()]
        market_date = date.astimezone(tz).date()
        
        # Standard market open times
        open_times = {
            'SYDNEY': time(9, 0),
            'TOKYO': time(9, 0),
            'LONDON': time(8, 0),
            'NEW_YORK': time(9, 30)
        }
        
        open_time = open_times.get(market.upper(), time(9, 0))
        market_open = tz.localize(datetime.combine(market_date, open_time))
        
        return market_open.astimezone(pytz.UTC)


class MarketHours:
    """Market hours and session detection."""
    
    @staticmethod
    def get_current_session(dt: datetime = None) -> MarketSession:
        """Get current market session."""
        if dt is None:
            dt = TimeUtils.now_utc()
        
        if TimeUtils.is_weekend(dt):
            return MarketSession.WEEKEND
        
        utc_time = dt.time()
        
        # Check for overlapping sessions first
        london_open = MarketSession.LONDON in MarketHours.get_active_sessions(dt)
        ny_open = MarketSession.NEW_YORK in MarketHours.get_active_sessions(dt)
        
        if london_open and ny_open:
            return MarketSession.OVERLAP_LONDON_NY
        
        # Check individual sessions (in UTC)
        if time(22, 0) <= utc_time or utc_time < time(6, 0):  # Sydney session
            return MarketSession.SYDNEY
        elif time(0, 0) <= utc_time < time(9, 0):  # Tokyo session
            return MarketSession.TOKYO
        elif time(8, 0) <= utc_time < time(17, 0):  # London session
            return MarketSession.LONDON
        elif time(13, 0) <= utc_time < time(22, 0):  # New York session
            return MarketSession.NEW_YORK
        else:
            return MarketSession.WEEKEND
    
    @staticmethod
    def get_active_sessions(dt: datetime = None) -> List[MarketSession]:
        """Get all currently active market sessions."""
        if dt is None:
            dt = TimeUtils.now_utc()
        
        if TimeUtils.is_weekend(dt):
            return []
        
        active_sessions = []
        utc_time = dt.time()
        
        # Check each session
        session_times_utc = {
            MarketSession.SYDNEY: (time(22, 0), time(6, 0)),     # 22:00 - 06:00 UTC
            MarketSession.TOKYO: (time(0, 0), time(9, 0)),       # 00:00 - 09:00 UTC
            MarketSession.LONDON: (time(8, 0), time(17, 0)),     # 08:00 - 17:00 UTC
            MarketSession.NEW_YORK: (time(13, 0), time(22, 0)),  # 13:00 - 22:00 UTC
        }
        
        for session, (start_time, end_time) in session_times_utc.items():
            if MarketHours._is_time_in_range(utc_time, start_time, end_time):
                active_sessions.append(session)
        
        return active_sessions
    
    @staticmethod
    def _is_time_in_range(current_time: time, start_time: time, end_time: time) -> bool:
        """Check if current time is within range (handling overnight sessions)."""
        if start_time <= end_time:
            # Same day session
            return start_time <= current_time <= end_time
        else:
            # Overnight session
            return current_time >= start_time or current_time <= end_time
    
    @staticmethod
    def is_market_open(market: str, dt: datetime = None) -> bool:
        """Check if specific market is open."""
        if dt is None:
            dt = TimeUtils.now_utc()
        
        if TimeUtils.is_weekend(dt):
            return False
        
        try:
            session = MarketSession[market.upper()]
            return session in MarketHours.get_active_sessions(dt)
        except KeyError:
            return False
    
    @staticmethod
    def next_market_open(market: str, dt: datetime = None) -> datetime:
        """Get next market open time."""
        if dt is None:
            dt = TimeUtils.now_utc()
        
        # If weekend, go to Monday
        if TimeUtils.is_weekend(dt):
            dt = TimeUtils.next_weekday(dt)
        
        return TimeUtils.market_open_time(market, dt)


class TimeWindow:
    """Time window calculations."""
    
    @staticmethod
    def get_window_start(window_size: timedelta, dt: datetime = None, align_to: str = 'floor') -> datetime:
        """Get start of time window."""
        if dt is None:
            dt = TimeUtils.now_utc()
        
        if align_to == 'floor':
            # Floor to window boundary
            total_seconds = int(window_size.total_seconds())
            timestamp = int(dt.timestamp())
            aligned_timestamp = (timestamp // total_seconds) * total_seconds
            return datetime.fromtimestamp(aligned_timestamp, tz=timezone.utc)
        elif align_to == 'ceil':
            # Ceiling to window boundary
            total_seconds = int(window_size.total_seconds())
            timestamp = int(dt.timestamp())
            aligned_timestamp = ((timestamp + total_seconds - 1) // total_seconds) * total_seconds
            return datetime.fromtimestamp(aligned_timestamp, tz=timezone.utc)
        else:
            return dt - window_size
    
    @staticmethod
    def get_time_buckets(start_time: datetime, end_time: datetime, bucket_size: timedelta) -> List[datetime]:
        """Generate time buckets between start and end time."""
        buckets = []
        current_time = start_time
        
        while current_time < end_time:
            buckets.append(current_time)
            current_time += bucket_size
        
        return buckets
    
    @staticmethod
    def time_until_next_window(window_size: timedelta, dt: datetime = None) -> timedelta:
        """Calculate time until next window boundary."""
        if dt is None:
            dt = TimeUtils.now_utc()
        
        next_window = TimeWindow.get_window_start(window_size, dt, align_to='ceil')
        return next_window - dt


class PeriodicTimer:
    """Periodic task execution."""
    
    def __init__(self, interval: timedelta, callback, start_immediately: bool = True):
        """
        Initialize periodic timer.
        
        Args:
            interval: Time interval between executions
            callback: Function to call periodically
            start_immediately: Whether to start immediately or wait for first interval
        """
        self.interval = interval
        self.callback = callback
        self._timer = None
        self._is_running = False
        self._lock = threading.Lock()
        
        if start_immediately:
            self.start()
    
    def start(self):
        """Start the periodic timer."""
        with self._lock:
            if not self._is_running:
                self._is_running = True
                self._schedule_next()
    
    def stop(self):
        """Stop the periodic timer."""
        with self._lock:
            self._is_running = False
            if self._timer:
                self._timer.cancel()
                self._timer = None
    
    def _schedule_next(self):
        """Schedule next execution."""
        if self._is_running:
            self._timer = threading.Timer(self.interval.total_seconds(), self._execute)
            self._timer.start()
    
    def _execute(self):
        """Execute callback and schedule next run."""
        try:
            self.callback()
        except Exception as e:
            # Log error but continue running
            print(f"Error in periodic timer callback: {e}")
        finally:
            self._schedule_next()


class RateLimiter:
    """Rate limiting utility."""
    
    def __init__(self, max_calls: int, time_window: timedelta):
        """
        Initialize rate limiter.
        
        Args:
            max_calls: Maximum calls allowed in time window
            time_window: Time window duration
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
        self._lock = threading.Lock()
    
    def can_proceed(self) -> bool:
        """Check if call can proceed without hitting rate limit."""
        with self._lock:
            now = TimeUtils.now_utc()
            cutoff = now - self.time_window
            
            # Remove old calls
            self.calls = [call_time for call_time in self.calls if call_time > cutoff]
            
            return len(self.calls) < self.max_calls
    
    def record_call(self) -> bool:
        """Record a call and return whether it was allowed."""
        with self._lock:
            if self.can_proceed():
                self.calls.append(TimeUtils.now_utc())
                return True
            return False
    
    def wait_time(self) -> float:
        """Get time to wait before next call is allowed."""
        with self._lock:
            if len(self.calls) < self.max_calls:
                return 0.0
            
            oldest_call = min(self.calls)
            wait_until = oldest_call + self.time_window
            wait_seconds = (wait_until - TimeUtils.now_utc()).total_seconds()
            
            return max(0.0, wait_seconds)


# Convenience functions
def sleep_until(target_time: datetime):
    """Sleep until target time."""
    wait_seconds = (target_time - TimeUtils.now_utc()).total_seconds()
    if wait_seconds > 0:
        time_module.sleep(wait_seconds)


def wait_for_next_minute():
    """Wait until the start of next minute."""
    now = TimeUtils.now_utc()
    next_minute = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    sleep_until(next_minute)


def wait_for_market_open(market: str):
    """Wait until market opens."""
    next_open = MarketHours.next_market_open(market)
    sleep_until(next_open)