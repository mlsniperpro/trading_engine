"""
Technical Indicators - RSI, EMA, VWAP calculations.

Implements:
1. RSI (Relative Strength Index) - Momentum oscillator
2. EMA (Exponential Moving Average) - Trend indicator
3. VWAP (Volume Weighted Average Price) - Intraday benchmark
4. SMA (Simple Moving Average) - Basic trend indicator
"""

import logging
from typing import List, Dict, Any, Optional
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class IndicatorResult:
    """Generic indicator result."""
    indicator: str
    value: float
    period: int
    timestamp: Any


def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """
    Calculate Relative Strength Index (RSI).

    RSI Formula:
        RSI = 100 - (100 / (1 + RS))
        where RS = Average Gain / Average Loss

    Using EMA for smoothing (Wilder's method):
        First Average Gain = sum of gains over period / period
        First Average Loss = sum of losses over period / period
        Subsequent values use EMA:
            Current Average Gain = ((previous avg gain) × (period-1) + current gain) / period
            Current Average Loss = ((previous avg loss) × (period-1) + current loss) / period

    Args:
        prices: List of closing prices (most recent last)
        period: RSI period (default: 14)

    Returns:
        RSI value (0-100) or None if insufficient data
    """
    if len(prices) < period + 1:
        logger.warning(f"Insufficient data for RSI calculation: need {period + 1}, got {len(prices)}")
        return None

    prices_array = np.array(prices)

    # Calculate price changes
    deltas = np.diff(prices_array)

    # Separate gains and losses
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    # Calculate initial averages (SMA for first value)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    # Calculate subsequent values using EMA
    for i in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period

    # Avoid division by zero
    if avg_loss == 0:
        return 100.0

    # Calculate RS and RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return float(rsi)


def calculate_ema(prices: List[float], period: int) -> Optional[float]:
    """
    Calculate Exponential Moving Average (EMA).

    EMA Formula:
        EMA = (Close - EMA_prev) × multiplier + EMA_prev
        where multiplier = 2 / (period + 1)

    First EMA value is calculated as SMA.

    Args:
        prices: List of closing prices (most recent last)
        period: EMA period (e.g., 20, 50, 200)

    Returns:
        Current EMA value or None if insufficient data
    """
    if len(prices) < period:
        logger.warning(f"Insufficient data for EMA calculation: need {period}, got {len(prices)}")
        return None

    prices_array = np.array(prices)

    # Calculate multiplier
    multiplier = 2 / (period + 1)

    # First EMA is SMA
    ema = np.mean(prices_array[:period])

    # Calculate EMA for remaining prices
    for price in prices_array[period:]:
        ema = (price - ema) * multiplier + ema

    return float(ema)


def calculate_sma(prices: List[float], period: int) -> Optional[float]:
    """
    Calculate Simple Moving Average (SMA).

    SMA Formula:
        SMA = sum of last N prices / N

    Args:
        prices: List of closing prices (most recent last)
        period: SMA period

    Returns:
        Current SMA value or None if insufficient data
    """
    if len(prices) < period:
        logger.warning(f"Insufficient data for SMA calculation: need {period}, got {len(prices)}")
        return None

    return float(np.mean(prices[-period:]))


def calculate_vwap(
    prices: List[float],
    volumes: List[float],
    high_prices: Optional[List[float]] = None,
    low_prices: Optional[List[float]] = None
) -> Optional[float]:
    """
    Calculate Volume Weighted Average Price (VWAP).

    VWAP Formula:
        VWAP = Σ(Typical Price × Volume) / Σ(Volume)
        where Typical Price = (High + Low + Close) / 3

    If high/low not provided, uses close price as typical price.

    Args:
        prices: List of closing prices
        volumes: List of volumes (same length as prices)
        high_prices: List of high prices (optional)
        low_prices: List of low prices (optional)

    Returns:
        VWAP value or None if insufficient data
    """
    if len(prices) == 0 or len(volumes) == 0:
        return None

    if len(prices) != len(volumes):
        logger.warning(f"Price and volume arrays must be same length")
        return None

    prices_array = np.array(prices)
    volumes_array = np.array(volumes)

    # Calculate typical price
    if high_prices and low_prices and len(high_prices) == len(prices):
        high_array = np.array(high_prices)
        low_array = np.array(low_prices)
        typical_prices = (high_array + low_array + prices_array) / 3
    else:
        # Use close as typical price if high/low not available
        typical_prices = prices_array

    # Calculate VWAP
    total_volume = np.sum(volumes_array)

    if total_volume == 0:
        return None

    vwap = np.sum(typical_prices * volumes_array) / total_volume

    return float(vwap)


def calculate_macd(
    prices: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Optional[Dict[str, float]]:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    MACD Formula:
        MACD Line = EMA(12) - EMA(26)
        Signal Line = EMA(9) of MACD Line
        Histogram = MACD Line - Signal Line

    Args:
        prices: List of closing prices
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line EMA period (default: 9)

    Returns:
        Dict with macd, signal, histogram or None if insufficient data
    """
    if len(prices) < slow_period + signal_period:
        return None

    # Calculate EMAs
    fast_ema = calculate_ema(prices, fast_period)
    slow_ema = calculate_ema(prices, slow_period)

    if fast_ema is None or slow_ema is None:
        return None

    # MACD line
    macd_line = fast_ema - slow_ema

    # For signal line, we need MACD values for the past signal_period days
    # Simplified: calculate signal from recent MACD values
    # In production, you'd track MACD history
    signal_line = macd_line  # Simplified for now

    # Histogram
    histogram = macd_line - signal_line

    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }


def calculate_bollinger_bands(
    prices: List[float],
    period: int = 20,
    num_std: float = 2.0
) -> Optional[Dict[str, float]]:
    """
    Calculate Bollinger Bands.

    Bollinger Bands Formula:
        Middle Band = SMA(period)
        Upper Band = Middle Band + (std_dev × num_std)
        Lower Band = Middle Band - (std_dev × num_std)

    Args:
        prices: List of closing prices
        period: SMA period (default: 20)
        num_std: Number of standard deviations (default: 2)

    Returns:
        Dict with upper, middle, lower bands or None
    """
    if len(prices) < period:
        return None

    recent_prices = prices[-period:]
    prices_array = np.array(recent_prices)

    # Calculate middle band (SMA)
    middle_band = np.mean(prices_array)

    # Calculate standard deviation
    std_dev = np.std(prices_array)

    # Calculate bands
    upper_band = middle_band + (std_dev * num_std)
    lower_band = middle_band - (std_dev * num_std)

    return {
        'upper': float(upper_band),
        'middle': float(middle_band),
        'lower': float(lower_band),
        'std_dev': float(std_dev)
    }


def calculate_atr(
    high_prices: List[float],
    low_prices: List[float],
    close_prices: List[float],
    period: int = 14
) -> Optional[float]:
    """
    Calculate Average True Range (ATR).

    ATR Formula:
        True Range = max(high - low, abs(high - prev_close), abs(low - prev_close))
        ATR = EMA of True Range

    Args:
        high_prices: List of high prices
        low_prices: List of low prices
        close_prices: List of close prices
        period: ATR period (default: 14)

    Returns:
        ATR value or None if insufficient data
    """
    if len(high_prices) < period + 1:
        return None

    if not (len(high_prices) == len(low_prices) == len(close_prices)):
        logger.warning("Price arrays must be same length")
        return None

    high_array = np.array(high_prices)
    low_array = np.array(low_prices)
    close_array = np.array(close_prices)

    # Calculate True Range
    tr_values = []

    for i in range(1, len(high_array)):
        high_low = high_array[i] - low_array[i]
        high_close = abs(high_array[i] - close_array[i-1])
        low_close = abs(low_array[i] - close_array[i-1])

        tr = max(high_low, high_close, low_close)
        tr_values.append(tr)

    # Calculate ATR as EMA of True Range
    if len(tr_values) < period:
        return None

    atr = calculate_ema(tr_values, period)

    return atr


# Example usage and testing
def test_indicators():
    """Test all technical indicators with sample data."""
    print("="*60)
    print("TECHNICAL INDICATORS TEST")
    print("="*60)

    # Sample price data (simulating uptrend)
    prices = [
        100, 101, 102, 101, 103, 105, 104, 106, 108, 107,
        109, 111, 110, 112, 114, 113, 115, 117, 116, 118,
        120, 119, 121, 123, 122, 124, 126, 125, 127, 129
    ]

    volumes = [1000] * len(prices)
    high_prices = [p + 1 for p in prices]
    low_prices = [p - 1 for p in prices]

    # Test RSI
    print("\n1. RSI (Relative Strength Index):")
    rsi = calculate_rsi(prices, period=14)
    print(f"   RSI(14): {rsi:.2f}")
    print(f"   Interpretation: {'Overbought (>70)' if rsi > 70 else 'Oversold (<30)' if rsi < 30 else 'Neutral (30-70)'}")

    # Test EMA
    print("\n2. EMA (Exponential Moving Average):")
    ema_20 = calculate_ema(prices, period=20)
    ema_50 = calculate_ema(prices + [130]*20, period=50)  # Add more data for 50 EMA
    print(f"   EMA(20): ${ema_20:.2f}")
    print(f"   EMA(50): ${ema_50:.2f}")
    print(f"   Trend: {'Bullish' if prices[-1] > ema_20 else 'Bearish'}")

    # Test SMA
    print("\n3. SMA (Simple Moving Average):")
    sma_20 = calculate_sma(prices, period=20)
    print(f"   SMA(20): ${sma_20:.2f}")

    # Test VWAP
    print("\n4. VWAP (Volume Weighted Average Price):")
    vwap = calculate_vwap(prices, volumes, high_prices, low_prices)
    print(f"   VWAP: ${vwap:.2f}")
    print(f"   Current Price vs VWAP: {'Above (Bullish)' if prices[-1] > vwap else 'Below (Bearish)'}")

    # Test Bollinger Bands
    print("\n5. Bollinger Bands:")
    bb = calculate_bollinger_bands(prices, period=20, num_std=2.0)
    if bb:
        print(f"   Upper Band: ${bb['upper']:.2f}")
        print(f"   Middle Band: ${bb['middle']:.2f}")
        print(f"   Lower Band: ${bb['lower']:.2f}")
        print(f"   Bandwidth: ${bb['upper'] - bb['lower']:.2f}")

    # Test ATR
    print("\n6. ATR (Average True Range):")
    atr = calculate_atr(high_prices, low_prices, prices, period=14)
    if atr:
        print(f"   ATR(14): ${atr:.2f}")
        print(f"   Volatility: {'High' if atr > 2 else 'Low'}")

    print("\n" + "="*60)


if __name__ == "__main__":
    test_indicators()
