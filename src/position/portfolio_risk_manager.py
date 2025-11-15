"""
Portfolio Risk Manager for comprehensive risk management.

Components:
- DumpDetector: Detect dumps before trailing stops hit
- CorrelationMonitor: Track BTC/ETH correlation and exit correlated positions
- PortfolioHealthMonitor: Score portfolio health (0-100) and trigger actions
- DrawdownCircuitBreaker: Daily drawdown protection (3%/4%/5% levels)
- HoldTimeEnforcer: Force close positions exceeding max hold time
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import deque
import statistics

from position.models import Position, PositionSide, AssetType, ExitReason, PositionState
from core.simple_events import (
    event_bus,
    DumpDetected,
    PortfolioHealthDegraded,
    CorrelatedDumpDetected,
    CircuitBreakerTriggered,
    MaxHoldTimeExceeded,
    ForceExitRequired,
    StopNewEntries,
    StopAllTrading,
)


logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class PortfolioHealth:
    """Portfolio health snapshot."""
    timestamp: datetime
    total_positions: int
    total_unrealized_pnl: float
    health_score: float  # 0-100
    btc_correlation_avg: float
    daily_drawdown_pct: float
    action_taken: str


@dataclass
class PriceHistory:
    """Price history for a symbol."""
    symbol: str
    prices: deque  # (timestamp, price) tuples
    max_size: int = 1000

    def add(self, price: float, timestamp: Optional[datetime] = None):
        """Add price to history."""
        if timestamp is None:
            timestamp = datetime.utcnow()

        self.prices.append((timestamp, price))

        # Keep only max_size entries
        if len(self.prices) > self.max_size:
            self.prices.popleft()

    def get_recent_prices(self, minutes: int) -> List[float]:
        """Get prices from last N minutes."""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        return [
            price for ts, price in self.prices
            if ts >= cutoff
        ]

    def get_price_change_pct(self, minutes: int) -> Optional[float]:
        """Get price change % over last N minutes."""
        recent = self.get_recent_prices(minutes)
        if len(recent) < 2:
            return None

        old_price = recent[0]
        new_price = recent[-1]
        return ((new_price - old_price) / old_price) * 100


# ============================================================================
# Dump Detector
# ============================================================================

class DumpDetector:
    """
    Detect early dump signals before trailing stop hits.

    Signals:
    1. Volume reversal (sell > buy for 3 candles)
    2. Order flow flip (2.5:1 buy → 2.5:1 sell)
    3. Momentum break (lower highs forming)
    """

    def __init__(self, config: Dict):
        """Initialize dump detector."""
        self.config = config.get('dump_detection', {})
        self.logger = logging.getLogger(f"{__name__}.DumpDetector")

        # Thresholds
        self.volume_reversal_candles = self.config.get('volume_reversal_candles', 3)
        self.order_flow_flip_ratio = self.config.get('order_flow_flip_ratio', 2.5)
        self.momentum_break_threshold = self.config.get('momentum_break_threshold', 3)

    async def detect_dump(
        self,
        position: Position,
        current_price: float,
        volume_data: Optional[Dict] = None,
        order_flow_data: Optional[Dict] = None
    ) -> bool:
        """
        Detect if position is dumping.

        Args:
            position: Position to check
            current_price: Current market price
            volume_data: Volume analysis data
            order_flow_data: Order flow analysis data

        Returns:
            True if dump detected
        """
        dump_signals = []

        # Signal 1: Volume reversal
        if volume_data:
            if self._check_volume_reversal(volume_data):
                dump_signals.append("volume_reversal")
                self.logger.warning(
                    f"[DUMP] Volume reversal detected for {position.symbol}"
                )

        # Signal 2: Order flow flip
        if order_flow_data:
            if self._check_order_flow_flip(order_flow_data):
                dump_signals.append("order_flow_flip")
                self.logger.warning(
                    f"[DUMP] Order flow flip detected for {position.symbol}"
                )

        # Signal 3: Momentum break (price action)
        if self._check_momentum_break(position, current_price):
            dump_signals.append("momentum_break")
            self.logger.warning(
                f"[DUMP] Momentum break detected for {position.symbol}"
            )

        # Trigger dump if 2+ signals detected
        if len(dump_signals) >= 2:
            self.logger.error(
                f"[DUMP] 🚨 DUMP DETECTED: {position.symbol} | "
                f"Signals: {dump_signals} | "
                f"P&L: {position.unrealized_pnl_pct:+.2f}%"
            )
            return True

        return False

    def _check_volume_reversal(self, volume_data: Dict) -> bool:
        """Check for volume reversal (sell > buy)."""
        # Get last N candles
        recent_candles = volume_data.get('recent_candles', [])
        if len(recent_candles) < self.volume_reversal_candles:
            return False

        # Check if sell volume > buy volume for N consecutive candles
        sell_dominant = 0
        for candle in recent_candles[-self.volume_reversal_candles:]:
            sell_vol = candle.get('sell_volume', 0)
            buy_vol = candle.get('buy_volume', 0)

            if sell_vol > buy_vol:
                sell_dominant += 1

        return sell_dominant >= self.volume_reversal_candles

    def _check_order_flow_flip(self, order_flow_data: Dict) -> bool:
        """Check for order flow flip (buy → sell dominance)."""
        current_ratio = order_flow_data.get('current_ratio', 1.0)
        previous_ratio = order_flow_data.get('previous_ratio', 1.0)

        # Was previously buy-heavy (> 2.5:1), now sell-heavy (< 0.4:1)
        if previous_ratio >= self.order_flow_flip_ratio and current_ratio <= (1 / self.order_flow_flip_ratio):
            return True

        return False

    def _check_momentum_break(self, position: Position, current_price: float) -> bool:
        """Check for momentum break (lower highs)."""
        # For long positions, check if price is making lower highs
        if position.side == PositionSide.LONG:
            if position.highest_price and current_price < position.highest_price * 0.995:
                # Price is 0.5% below recent high and falling
                return True

        # For short positions, check if price is making higher lows
        elif position.side == PositionSide.SHORT:
            if position.lowest_price and current_price > position.lowest_price * 1.005:
                # Price is 0.5% above recent low and rising
                return True

        return False


# ============================================================================
# Correlation Monitor
# ============================================================================

class CorrelationMonitor:
    """
    Monitor BTC/ETH correlation and exit correlated positions on dumps.

    Tracks:
    - BTC/ETH price movements
    - Position correlations with market leaders
    - Triggers exits on correlated dumps
    """

    def __init__(self, config: Dict):
        """Initialize correlation monitor."""
        self.config = config.get('correlation', {})
        self.logger = logging.getLogger(f"{__name__}.CorrelationMonitor")

        # Price history
        self.price_history: Dict[str, PriceHistory] = {
            'BTC': PriceHistory('BTC', deque()),
            'ETH': PriceHistory('ETH', deque()),
        }

        # Thresholds
        self.dump_threshold_pct = self.config.get('dump_threshold_pct', 1.5)
        self.dump_timeframe_minutes = self.config.get('dump_timeframe_minutes', 5)
        self.correlation_threshold = self.config.get('correlation_threshold', 0.7)

    async def update_price(self, symbol: str, price: float):
        """Update price for market leader."""
        if symbol in ['BTC', 'BTCUSDT', 'BTC-USDT']:
            self.price_history['BTC'].add(price)
        elif symbol in ['ETH', 'ETHUSDT', 'ETH-USDT']:
            self.price_history['ETH'].add(price)

    async def check_market_leader_dump(self) -> Optional[Tuple[str, float]]:
        """
        Check if BTC or ETH is dumping.

        Returns:
            Tuple of (symbol, dump_pct) if dump detected, else None
        """
        for symbol in ['BTC', 'ETH']:
            history = self.price_history[symbol]
            dump_pct = history.get_price_change_pct(self.dump_timeframe_minutes)

            if dump_pct and dump_pct <= -self.dump_threshold_pct:
                self.logger.error(
                    f"[CORR] 🚨 {symbol} DUMP: {dump_pct:.2f}% in {self.dump_timeframe_minutes}m"
                )
                return (symbol, dump_pct)

        return None

    def calculate_correlation(
        self,
        position: Position,
        leader_symbol: str
    ) -> float:
        """
        Calculate correlation between position and market leader.

        Args:
            position: Position to check
            leader_symbol: BTC or ETH

        Returns:
            Correlation coefficient (-1 to 1)
        """
        # Simple correlation: if both crypto, assume positive correlation
        # In production, you'd calculate actual correlation from price history

        # Major crypto correlated with BTC/ETH
        if position.asset_type in [AssetType.CRYPTO_MAJOR, AssetType.CRYPTO_REGULAR]:
            return 0.75  # Default high correlation

        # Meme coins less correlated
        if position.asset_type == AssetType.CRYPTO_MEME:
            return 0.4  # Lower correlation

        return 0.5

    async def get_correlated_positions(
        self,
        positions: Dict[str, Position],
        leader_symbol: str
    ) -> List[Position]:
        """
        Get positions highly correlated with market leader.

        Args:
            positions: All open positions
            leader_symbol: BTC or ETH

        Returns:
            List of correlated positions
        """
        correlated = []

        for pos in positions.values():
            if pos.state != PositionState.OPEN:
                continue

            correlation = self.calculate_correlation(pos, leader_symbol)

            if correlation >= self.correlation_threshold:
                correlated.append(pos)

        return correlated


# ============================================================================
# Portfolio Health Monitor
# ============================================================================

class PortfolioHealthMonitor:
    """
    Monitor portfolio health and score 0-100.

    Factors:
    - Total P&L
    - Win rate
    - Position quality
    - Concentration risk
    - Hold time distribution
    """

    def __init__(self, config: Dict):
        """Initialize health monitor."""
        self.config = config.get('health', {})
        self.logger = logging.getLogger(f"{__name__}.PortfolioHealthMonitor")

    async def calculate_health(
        self,
        positions: Dict[str, Position]
    ) -> PortfolioHealth:
        """
        Calculate portfolio health score.

        Args:
            positions: All open positions

        Returns:
            PortfolioHealth object
        """
        open_positions = [p for p in positions.values() if p.state == PositionState.OPEN]

        if not open_positions:
            return PortfolioHealth(
                timestamp=datetime.utcnow(),
                total_positions=0,
                total_unrealized_pnl=0.0,
                health_score=100.0,
                btc_correlation_avg=0.0,
                daily_drawdown_pct=0.0,
                action_taken="none"
            )

        # Calculate metrics
        total_pnl = sum(p.unrealized_pnl for p in open_positions)
        profitable_count = sum(1 for p in open_positions if p.is_profitable())
        win_rate = profitable_count / len(open_positions) if open_positions else 0

        # Health score components
        pnl_score = self._score_pnl(total_pnl)
        quality_score = self._score_quality(open_positions, win_rate)
        concentration_score = self._score_concentration(open_positions)
        hold_time_score = self._score_hold_times(open_positions)

        # Weighted health score
        health_score = (
            pnl_score * 0.4 +
            quality_score * 0.3 +
            concentration_score * 0.2 +
            hold_time_score * 0.1
        )

        return PortfolioHealth(
            timestamp=datetime.utcnow(),
            total_positions=len(open_positions),
            total_unrealized_pnl=total_pnl,
            health_score=health_score,
            btc_correlation_avg=0.0,  # Would calculate from correlation monitor
            daily_drawdown_pct=0.0,   # Would calculate from circuit breaker
            action_taken="none"
        )

    def _score_pnl(self, total_pnl: float) -> float:
        """Score based on total P&L (0-100)."""
        if total_pnl >= 100:
            return 100.0
        elif total_pnl >= 50:
            return 80.0
        elif total_pnl >= 0:
            return 60.0
        elif total_pnl >= -50:
            return 40.0
        elif total_pnl >= -100:
            return 20.0
        else:
            return 0.0

    def _score_quality(self, positions: List[Position], win_rate: float) -> float:
        """Score based on position quality (0-100)."""
        # Win rate component (60%)
        win_score = win_rate * 100

        # Average P&L% component (40%)
        avg_pnl_pct = sum(p.unrealized_pnl_pct for p in positions) / len(positions)
        pnl_pct_score = min(max((avg_pnl_pct + 2) * 25, 0), 100)  # -2% to +2% → 0 to 100

        return win_score * 0.6 + pnl_pct_score * 0.4

    def _score_concentration(self, positions: List[Position]) -> float:
        """Score based on concentration risk (0-100)."""
        # Count unique symbols
        unique_symbols = len(set(p.symbol for p in positions))

        # More diversification = better score
        if unique_symbols >= 5:
            return 100.0
        elif unique_symbols >= 3:
            return 80.0
        elif unique_symbols >= 2:
            return 60.0
        else:
            return 40.0  # All eggs in one basket

    def _score_hold_times(self, positions: List[Position]) -> float:
        """Score based on hold time distribution (0-100)."""
        hold_times = [p.get_hold_time_minutes() for p in positions]
        avg_hold = sum(hold_times) / len(hold_times)

        # Prefer shorter hold times for scalping
        if avg_hold <= 30:
            return 100.0
        elif avg_hold <= 60:
            return 80.0
        elif avg_hold <= 120:
            return 60.0
        else:
            return 40.0


# ============================================================================
# Drawdown Circuit Breaker
# ============================================================================

class DrawdownCircuitBreaker:
    """
    Daily drawdown circuit breaker.

    Levels:
    - 3% drawdown: Close worst 50% of positions
    - 4% drawdown: Close ALL positions
    - 5% drawdown: Close all + STOP TRADING
    """

    def __init__(self, config: Dict):
        """Initialize circuit breaker."""
        self.config = config.get('circuit_breaker', {})
        self.logger = logging.getLogger(f"{__name__}.DrawdownCircuitBreaker")

        # Thresholds
        self.level_1_pct = self.config.get('level_1_pct', 3.0)
        self.level_2_pct = self.config.get('level_2_pct', 4.0)
        self.level_3_pct = self.config.get('level_3_pct', 5.0)

        # State
        self.session_start_balance = 0.0
        self.daily_pnl = 0.0
        self.triggered_levels = set()

    def set_session_start_balance(self, balance: float):
        """Set starting balance for the day."""
        self.session_start_balance = balance
        self.daily_pnl = 0.0
        self.triggered_levels = set()
        self.logger.info(f"[CB] Session start balance: ${balance:.2f}")

    def update_daily_pnl(self, current_pnl: float):
        """Update daily P&L."""
        self.daily_pnl = current_pnl

    def get_drawdown_pct(self) -> float:
        """Get current drawdown percentage."""
        if self.session_start_balance == 0:
            return 0.0

        return (self.daily_pnl / self.session_start_balance) * 100

    def should_trigger(self) -> Optional[int]:
        """
        Check if circuit breaker should trigger.

        Returns:
            Circuit breaker level (1, 2, or 3) or None
        """
        drawdown_pct = abs(self.get_drawdown_pct())

        # Check level 3 (most severe)
        if drawdown_pct >= self.level_3_pct and 3 not in self.triggered_levels:
            self.triggered_levels.add(3)
            return 3

        # Check level 2
        if drawdown_pct >= self.level_2_pct and 2 not in self.triggered_levels:
            self.triggered_levels.add(2)
            return 2

        # Check level 1
        if drawdown_pct >= self.level_1_pct and 1 not in self.triggered_levels:
            self.triggered_levels.add(1)
            return 1

        return None


# ============================================================================
# Hold Time Enforcer
# ============================================================================

class HoldTimeEnforcer:
    """
    Enforce maximum hold times.

    Limits:
    - Scalping: 30 min max
    - Meme coins: 24 hours max
    - Forex: Close before session end
    """

    def __init__(self, config: Dict):
        """Initialize hold time enforcer."""
        self.config = config.get('hold_time', {})
        self.logger = logging.getLogger(f"{__name__}.HoldTimeEnforcer")

        # Max hold times (minutes)
        self.max_hold_scalping = self.config.get('max_hold_scalping', 30)
        self.max_hold_meme = self.config.get('max_hold_meme', 1440)  # 24 hours
        self.max_hold_forex = self.config.get('max_hold_forex', 240)  # 4 hours

    async def check_hold_times(
        self,
        positions: Dict[str, Position]
    ) -> List[Position]:
        """
        Check for positions exceeding max hold time.

        Args:
            positions: All open positions

        Returns:
            List of positions to force close
        """
        to_close = []

        for pos in positions.values():
            if pos.state != PositionState.OPEN:
                continue

            hold_time = pos.get_hold_time_minutes()
            max_hold = self._get_max_hold_time(pos)

            if hold_time >= max_hold:
                self.logger.warning(
                    f"[HOLD] Max hold time exceeded: {pos.symbol} | "
                    f"Hold: {hold_time:.1f}m / Max: {max_hold}m"
                )
                to_close.append(pos)

        return to_close

    def _get_max_hold_time(self, position: Position) -> float:
        """Get max hold time for position."""
        if position.asset_type == AssetType.CRYPTO_MEME:
            return self.max_hold_meme

        if position.asset_type == AssetType.FOREX:
            return self.max_hold_forex

        # Default scalping
        return self.max_hold_scalping


# ============================================================================
# Portfolio Risk Manager (Main Orchestrator)
# ============================================================================

class PortfolioRiskManager:
    """
    Portfolio-level risk management orchestrator.

    Runs 24/7 monitoring all positions and portfolio health.
    """

    def __init__(self, config: Dict):
        """Initialize portfolio risk manager."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.PortfolioRiskManager")

        # Sub-components
        self.dump_detector = DumpDetector(config)
        self.correlation_monitor = CorrelationMonitor(config)
        self.health_monitor = PortfolioHealthMonitor(config)
        self.circuit_breaker = DrawdownCircuitBreaker(config)
        self.hold_time_enforcer = HoldTimeEnforcer(config)

        # State
        self.open_positions: Dict[str, Position] = {}
        self.is_running = False
        self.monitoring_task = None

    async def start(self, trailing_stop_manager):
        """
        Start portfolio monitoring.

        Args:
            trailing_stop_manager: TrailingStopManager instance
        """
        self.trailing_stop_manager = trailing_stop_manager
        self.is_running = True

        # Start monitoring loop
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())

        self.logger.info("[PRM] Portfolio Risk Manager started (24/7 monitoring)")

    async def stop(self):
        """Stop portfolio monitoring."""
        self.is_running = False

        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        self.logger.info("[PRM] Portfolio Risk Manager stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop (runs every 10 seconds)."""
        while self.is_running:
            try:
                await self._monitor_portfolio()
                await asyncio.sleep(10)  # Check every 10 seconds
            except Exception as e:
                self.logger.error(f"[PRM] Error in monitoring loop: {e}")
                await asyncio.sleep(10)

    async def _monitor_portfolio(self):
        """Monitor portfolio health and take actions."""
        # Get open positions from trailing stop manager
        self.open_positions = self.trailing_stop_manager.get_all_positions()

        if not self.open_positions:
            return

        # 1. Check hold times
        await self._check_hold_times()

        # 2. Check portfolio health
        await self._check_portfolio_health()

        # 3. Check market leader dumps (BTC/ETH)
        await self._check_correlated_dumps()

        # 4. Check circuit breaker
        await self._check_circuit_breaker()

    async def _check_hold_times(self):
        """Check and enforce max hold times."""
        to_close = await self.hold_time_enforcer.check_hold_times(self.open_positions)

        for pos in to_close:
            await self._force_close_position(
                pos,
                ExitReason.MAX_HOLD_TIME,
                "Maximum hold time exceeded"
            )

    async def _check_portfolio_health(self):
        """Check portfolio health and take action."""
        health = await self.health_monitor.calculate_health(self.open_positions)

        if health.health_score < 30:
            # CRITICAL: Close worst 2 positions
            self.logger.error(
                f"[PRM] 🚨 CRITICAL HEALTH: {health.health_score:.1f}/100 | "
                f"Closing worst 2 positions"
            )
            await self._close_worst_positions(2)

            event = PortfolioHealthDegraded(
                timestamp=datetime.utcnow(),
                metadata={"health": health.__dict__, "action": "closed_worst_2"}
            )
            await event_bus.publish(event)

        elif health.health_score < 50:
            # WARNING: Tighten all stops
            self.logger.warning(
                f"[PRM] ⚠ LOW HEALTH: {health.health_score:.1f}/100 | "
                f"Tightening all stops to 0.3%"
            )
            await self._tighten_all_stops(0.3)

        elif health.health_score < 70:
            # CAUTION: Stop new entries
            event = StopNewEntries(
                timestamp=datetime.utcnow(),
                metadata={"reason": "Portfolio health degraded", "health_score": health.health_score}
            )
            await event_bus.publish(event)

    async def _check_correlated_dumps(self):
        """Check for BTC/ETH dumps and exit correlated positions."""
        dump_info = await self.correlation_monitor.check_market_leader_dump()

        if dump_info:
            leader_symbol, dump_pct = dump_info

            # Get correlated positions
            correlated = await self.correlation_monitor.get_correlated_positions(
                self.open_positions,
                leader_symbol
            )

            if correlated:
                self.logger.error(
                    f"[PRM] 🚨 {leader_symbol} DUMP ({dump_pct:.2f}%) | "
                    f"Exiting {len(correlated)} correlated positions"
                )

                for pos in correlated:
                    await self._force_close_position(
                        pos,
                        ExitReason.CORRELATION_EXIT,
                        f"{leader_symbol} dump detected"
                    )

    async def _check_circuit_breaker(self):
        """Check circuit breaker and take action."""
        level = self.circuit_breaker.should_trigger()

        if level == 3:
            # Level 3: Close all + stop trading
            self.logger.error(
                f"[PRM] 🚨🚨🚨 CIRCUIT BREAKER LEVEL 3 | "
                f"Drawdown: {self.circuit_breaker.get_drawdown_pct():.2f}% | "
                f"CLOSING ALL + STOPPING TRADING"
            )
            await self._close_all_positions()

            event = StopAllTrading(
                timestamp=datetime.utcnow(),
                metadata={"reason": "Circuit breaker level 3", "drawdown_pct": self.circuit_breaker.get_drawdown_pct()}
            )
            await event_bus.publish(event)

        elif level == 2:
            # Level 2: Close all positions
            self.logger.error(
                f"[PRM] 🚨🚨 CIRCUIT BREAKER LEVEL 2 | "
                f"Drawdown: {self.circuit_breaker.get_drawdown_pct():.2f}% | "
                f"CLOSING ALL POSITIONS"
            )
            await self._close_all_positions()

        elif level == 1:
            # Level 1: Close worst 50%
            self.logger.warning(
                f"[PRM] 🚨 CIRCUIT BREAKER LEVEL 1 | "
                f"Drawdown: {self.circuit_breaker.get_drawdown_pct():.2f}% | "
                f"Closing worst 50% of positions"
            )
            num_to_close = max(1, len(self.open_positions) // 2)
            await self._close_worst_positions(num_to_close)

    async def _force_close_position(
        self,
        position: Position,
        exit_reason: ExitReason,
        reason_text: str
    ):
        """Force close a position."""
        if position.current_price:
            await self.trailing_stop_manager.manual_exit(
                position.position_id,
                position.current_price,
                reason_text
            )

    async def _close_worst_positions(self, count: int):
        """Close worst N positions by P&L."""
        # Sort by P&L (worst first)
        sorted_positions = sorted(
            self.open_positions.values(),
            key=lambda p: p.unrealized_pnl
        )

        # Close worst N
        for pos in sorted_positions[:count]:
            await self._force_close_position(
                pos,
                ExitReason.PORTFOLIO_HEALTH,
                "Portfolio health action"
            )

    async def _close_all_positions(self):
        """Close all positions."""
        for pos in list(self.open_positions.values()):
            await self._force_close_position(
                pos,
                ExitReason.CIRCUIT_BREAKER,
                "Circuit breaker triggered"
            )

    async def _tighten_all_stops(self, new_trailing_pct: float):
        """Tighten all trailing stops."""
        for pos in self.open_positions.values():
            if pos.trailing_stop_distance_pct > new_trailing_pct:
                pos.trailing_stop_distance_pct = new_trailing_pct
                self.logger.info(
                    f"[PRM] Tightened {pos.symbol} stop to {new_trailing_pct}%"
                )
