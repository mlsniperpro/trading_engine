"""
Mathematical Utilities

Provides mathematical functions for:
- Statistical calculations
- Risk metrics
- Price analysis
- Performance calculations
"""

import math
import numpy as np
from typing import List, Tuple, Optional, Union
from scipy import stats
import pandas as pd


class StatisticalUtils:
    """Statistical calculation utilities."""
    
    @staticmethod
    def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
        """Safe division that handles zero denominators."""
        if denominator == 0 or math.isnan(denominator):
            return default
        return numerator / denominator
    
    @staticmethod
    def z_score(value: float, mean: float, std: float) -> float:
        """Calculate z-score (standard deviations from mean)."""
        if std == 0:
            return 0.0
        return (value - mean) / std
    
    @staticmethod
    def percentile(data: List[float], percentile: float) -> float:
        """Calculate percentile value."""
        if not data:
            return 0.0
        return np.percentile(data, percentile)
    
    @staticmethod
    def rolling_mean(data: List[float], window: int) -> List[float]:
        """Calculate rolling mean."""
        if len(data) < window:
            return data
        
        result = []
        for i in range(len(data)):
            if i < window - 1:
                result.append(np.mean(data[:i+1]))
            else:
                result.append(np.mean(data[i-window+1:i+1]))
        return result
    
    @staticmethod
    def rolling_std(data: List[float], window: int) -> List[float]:
        """Calculate rolling standard deviation."""
        if len(data) < window:
            return [np.std(data[:i+1]) for i in range(len(data))]
        
        result = []
        for i in range(len(data)):
            if i < window - 1:
                result.append(np.std(data[:i+1]))
            else:
                result.append(np.std(data[i-window+1:i+1]))
        return result
    
    @staticmethod
    def correlation(x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        
        try:
            return np.corrcoef(x, y)[0, 1]
        except:
            return 0.0
    
    @staticmethod
    def linear_regression(x: List[float], y: List[float]) -> Tuple[float, float, float]:
        """
        Calculate linear regression.
        
        Returns:
            Tuple of (slope, intercept, r_squared)
        """
        if len(x) != len(y) or len(x) < 2:
            return 0.0, 0.0, 0.0
        
        try:
            slope, intercept, r_value, _, _ = stats.linregress(x, y)
            return slope, intercept, r_value ** 2
        except:
            return 0.0, 0.0, 0.0


class RiskMetrics:
    """Risk calculation utilities."""
    
    @staticmethod
    def value_at_risk(returns: List[float], confidence: float = 0.95) -> float:
        """Calculate Value at Risk (VaR)."""
        if not returns:
            return 0.0
        
        alpha = 1 - confidence
        return np.percentile(returns, alpha * 100)
    
    @staticmethod
    def conditional_value_at_risk(returns: List[float], confidence: float = 0.95) -> float:
        """Calculate Conditional Value at Risk (CVaR/Expected Shortfall)."""
        if not returns:
            return 0.0
        
        var = RiskMetrics.value_at_risk(returns, confidence)
        tail_losses = [r for r in returns if r <= var]
        
        if not tail_losses:
            return var
        
        return np.mean(tail_losses)
    
    @staticmethod
    def sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio."""
        if not returns:
            return 0.0
        
        excess_returns = [r - risk_free_rate for r in returns]
        mean_excess = np.mean(excess_returns)
        std_excess = np.std(excess_returns)
        
        return StatisticalUtils.safe_divide(mean_excess, std_excess)
    
    @staticmethod
    def sortino_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
        """Calculate Sortino ratio (downside deviation)."""
        if not returns:
            return 0.0
        
        excess_returns = [r - risk_free_rate for r in returns]
        mean_excess = np.mean(excess_returns)
        
        # Calculate downside deviation
        negative_returns = [r for r in excess_returns if r < 0]
        if not negative_returns:
            return float('inf') if mean_excess > 0 else 0.0
        
        downside_std = np.std(negative_returns)
        return StatisticalUtils.safe_divide(mean_excess, downside_std)
    
    @staticmethod
    def maximum_drawdown(values: List[float]) -> Tuple[float, int, int]:
        """
        Calculate maximum drawdown.
        
        Returns:
            Tuple of (max_drawdown, start_index, end_index)
        """
        if not values:
            return 0.0, 0, 0
        
        peak = values[0]
        max_dd = 0.0
        start_idx = 0
        end_idx = 0
        temp_start = 0
        
        for i, value in enumerate(values):
            if value > peak:
                peak = value
                temp_start = i
            
            drawdown = (peak - value) / peak
            if drawdown > max_dd:
                max_dd = drawdown
                start_idx = temp_start
                end_idx = i
        
        return max_dd, start_idx, end_idx
    
    @staticmethod
    def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Calculate Kelly criterion optimal bet size."""
        if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
            return 0.0
        
        lose_rate = 1 - win_rate
        b = avg_win / avg_loss  # Ratio of win to loss
        
        kelly_fraction = (b * win_rate - lose_rate) / b
        return max(0.0, min(kelly_fraction, 1.0))  # Cap at 100%


class PriceAnalysis:
    """Price analysis utilities."""
    
    @staticmethod
    def log_returns(prices: List[float]) -> List[float]:
        """Calculate logarithmic returns."""
        if len(prices) < 2:
            return []
        
        return [math.log(prices[i] / prices[i-1]) for i in range(1, len(prices))]
    
    @staticmethod
    def simple_returns(prices: List[float]) -> List[float]:
        """Calculate simple returns."""
        if len(prices) < 2:
            return []
        
        return [(prices[i] / prices[i-1]) - 1 for i in range(1, len(prices))]
    
    @staticmethod
    def volatility(prices: List[float], periods_per_year: int = 252) -> float:
        """Calculate annualized volatility."""
        returns = PriceAnalysis.log_returns(prices)
        if not returns:
            return 0.0
        
        return np.std(returns) * math.sqrt(periods_per_year)
    
    @staticmethod
    def price_momentum(prices: List[float], window: int) -> List[float]:
        """Calculate price momentum over window."""
        if len(prices) < window:
            return []
        
        momentum = []
        for i in range(window, len(prices)):
            mom = (prices[i] / prices[i - window]) - 1
            momentum.append(mom)
        
        return momentum
    
    @staticmethod
    def bollinger_bands(prices: List[float], window: int = 20, num_std: float = 2.0) -> Tuple[List[float], List[float], List[float]]:
        """
        Calculate Bollinger Bands.
        
        Returns:
            Tuple of (upper_band, middle_band, lower_band)
        """
        if len(prices) < window:
            return [], [], []
        
        middle_band = StatisticalUtils.rolling_mean(prices, window)
        rolling_std = StatisticalUtils.rolling_std(prices, window)
        
        upper_band = [middle_band[i] + (num_std * rolling_std[i]) for i in range(len(middle_band))]
        lower_band = [middle_band[i] - (num_std * rolling_std[i]) for i in range(len(middle_band))]
        
        return upper_band, middle_band, lower_band
    
    @staticmethod
    def rsi(prices: List[float], window: int = 14) -> List[float]:
        """Calculate Relative Strength Index."""
        if len(prices) < window + 1:
            return []
        
        changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [max(0, change) for change in changes]
        losses = [max(0, -change) for change in changes]
        
        rsi_values = []
        
        # Calculate first RSI value
        avg_gain = np.mean(gains[:window])
        avg_loss = np.mean(losses[:window])
        
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            rsi_values.append(rsi)
        
        # Calculate subsequent RSI values using smoothed averages
        for i in range(window, len(changes)):
            avg_gain = (avg_gain * (window - 1) + gains[i]) / window
            avg_loss = (avg_loss * (window - 1) + losses[i]) / window
            
            if avg_loss == 0:
                rsi_values.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
                rsi_values.append(rsi)
        
        return rsi_values


class PositionSizing:
    """Position sizing utilities."""
    
    @staticmethod
    def fixed_fractional(account_balance: float, risk_per_trade: float, stop_loss_pct: float) -> float:
        """Calculate position size using fixed fractional method."""
        if stop_loss_pct <= 0:
            return 0.0
        
        risk_amount = account_balance * risk_per_trade
        position_size = risk_amount / stop_loss_pct
        
        return position_size
    
    @staticmethod
    def volatility_adjusted(account_balance: float, target_volatility: float, price_volatility: float) -> float:
        """Calculate position size adjusted for volatility."""
        if price_volatility <= 0:
            return 0.0
        
        volatility_ratio = target_volatility / price_volatility
        return account_balance * volatility_ratio
    
    @staticmethod
    def kelly_position_size(account_balance: float, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Calculate position size using Kelly criterion."""
        kelly_fraction = RiskMetrics.kelly_criterion(win_rate, avg_win, avg_loss)
        return account_balance * kelly_fraction * 0.25  # Conservative 25% of Kelly


class TechnicalUtils:
    """Technical analysis utilities."""
    
    @staticmethod
    def ema(prices: List[float], period: int) -> List[float]:
        """Calculate Exponential Moving Average."""
        if not prices or period <= 0:
            return []
        
        multiplier = 2.0 / (period + 1)
        ema_values = [prices[0]]  # Start with first price
        
        for price in prices[1:]:
            ema_value = (price * multiplier) + (ema_values[-1] * (1 - multiplier))
            ema_values.append(ema_value)
        
        return ema_values
    
    @staticmethod
    def sma(prices: List[float], period: int) -> List[float]:
        """Calculate Simple Moving Average."""
        return StatisticalUtils.rolling_mean(prices, period)
    
    @staticmethod
    def vwap(prices: List[float], volumes: List[float]) -> List[float]:
        """Calculate Volume Weighted Average Price."""
        if len(prices) != len(volumes) or not prices:
            return []
        
        vwap_values = []
        cumulative_volume = 0
        cumulative_pv = 0
        
        for i, (price, volume) in enumerate(zip(prices, volumes)):
            cumulative_pv += price * volume
            cumulative_volume += volume
            
            if cumulative_volume > 0:
                vwap_values.append(cumulative_pv / cumulative_volume)
            else:
                vwap_values.append(price)
        
        return vwap_values
    
    @staticmethod
    def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
        """Calculate Average True Range."""
        if len(highs) != len(lows) or len(highs) != len(closes) or len(highs) < 2:
            return []
        
        true_ranges = []
        
        for i in range(1, len(highs)):
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i-1])
            tr3 = abs(lows[i] - closes[i-1])
            true_ranges.append(max(tr1, tr2, tr3))
        
        return StatisticalUtils.rolling_mean(true_ranges, period)


# Utility functions for common calculations
def compound_returns(returns: List[float]) -> float:
    """Calculate compound return from list of returns."""
    if not returns:
        return 0.0
    
    compound = 1.0
    for ret in returns:
        compound *= (1.0 + ret)
    
    return compound - 1.0


def annualize_return(total_return: float, days: int) -> float:
    """Annualize a total return."""
    if days <= 0:
        return 0.0
    
    years = days / 365.25
    return ((1.0 + total_return) ** (1.0 / years)) - 1.0


def normalize_weights(weights: List[float]) -> List[float]:
    """Normalize weights to sum to 1.0."""
    total = sum(weights)
    if total == 0:
        return weights
    
    return [w / total for w in weights]


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value between min and max."""
    return max(min_val, min(value, max_val))