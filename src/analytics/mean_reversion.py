"""
Mean Reversion Analytics Module

Calculates statistical metrics for mean reversion strategies:
- Rolling price means and standard deviations
- Z-scores and statistical extremes
- Mean reversion signals and thresholds

Supports the MeanReversionFilter in the decision engine.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MeanReversionMetrics:
    """Container for mean reversion analytics results."""
    price_mean_15m: float
    price_std_dev_15m: float
    price_mean_1h: float
    price_std_dev_1h: float
    z_score_15m: float
    z_score_1h: float
    deviation_magnitude: float
    reversion_probability: float
    extreme_level: str  # 'normal', 'moderate', 'extreme'


class MeanReversionAnalyzer:
    """
    Analyzes price data for mean reversion opportunities.
    
    Uses statistical measures to identify when price has deviated
    significantly from its recent mean, indicating potential reversion.
    """

    def __init__(self, 
                 short_window: int = 15,  # 15 minutes
                 long_window: int = 60):   # 1 hour
        """
        Initialize mean reversion analyzer.
        
        Args:
            short_window: Short-term lookback period in minutes
            long_window: Long-term lookback period in minutes
        """
        self.short_window = short_window
        self.long_window = long_window
        logger.info(f"MeanReversionAnalyzer initialized (short={short_window}m, long={long_window}m)")

    def analyze(self, price_data: List[Dict[str, Any]]) -> Optional[MeanReversionMetrics]:
        """
        Analyze price data for mean reversion signals.
        
        Args:
            price_data: List of price records with timestamp and price
            
        Returns:
            MeanReversionMetrics or None if insufficient data
        """
        try:
            if len(price_data) < self.long_window:
                logger.warning(f"Insufficient data: {len(price_data)} < {self.long_window}")
                return None

            # Convert to pandas for easier analysis
            df = pd.DataFrame(price_data)
            if 'price' not in df.columns:
                logger.error("Price column missing from data")
                return None

            prices = df['price'].astype(float)
            current_price = prices.iloc[-1]

            # Calculate rolling means and standard deviations
            price_mean_15m = prices.tail(self.short_window).mean()
            price_std_15m = prices.tail(self.short_window).std()
            price_mean_1h = prices.tail(self.long_window).mean()
            price_std_1h = prices.tail(self.long_window).std()

            # Calculate z-scores
            z_score_15m = (current_price - price_mean_15m) / price_std_15m if price_std_15m > 0 else 0.0
            z_score_1h = (current_price - price_mean_1h) / price_std_1h if price_std_1h > 0 else 0.0

            # Calculate deviation magnitude (using 15m as primary)
            deviation_magnitude = abs(z_score_15m)

            # Determine extreme level and reversion probability
            if deviation_magnitude >= 2.0:
                extreme_level = "extreme"
                reversion_probability = 0.95  # ~95% chance based on normal distribution
            elif deviation_magnitude >= 1.0:
                extreme_level = "moderate"
                reversion_probability = 0.68  # ~68% chance
            else:
                extreme_level = "normal"
                reversion_probability = 0.50  # No statistical edge

            return MeanReversionMetrics(
                price_mean_15m=float(price_mean_15m),
                price_std_dev_15m=float(price_std_15m),
                price_mean_1h=float(price_mean_1h),
                price_std_dev_1h=float(price_std_1h),
                z_score_15m=float(z_score_15m),
                z_score_1h=float(z_score_1h),
                deviation_magnitude=float(deviation_magnitude),
                reversion_probability=float(reversion_probability),
                extreme_level=extreme_level
            )

        except Exception as e:
            logger.error(f"Error in mean reversion analysis: {e}")
            return None

    def calculate_rolling_statistics(self, 
                                   prices: np.ndarray, 
                                   window: int) -> Tuple[float, float]:
        """
        Calculate rolling mean and standard deviation.
        
        Args:
            prices: Array of price values
            window: Rolling window size
            
        Returns:
            Tuple of (mean, std_dev)
        """
        if len(prices) < window:
            return float(np.mean(prices)), float(np.std(prices))
        
        recent_prices = prices[-window:]
        return float(np.mean(recent_prices)), float(np.std(recent_prices))

    def detect_statistical_extremes(self, 
                                   current_price: float,
                                   mean_price: float, 
                                   std_dev: float) -> Dict[str, Any]:
        """
        Detect if current price is at statistical extreme.
        
        Args:
            current_price: Current market price
            mean_price: Rolling mean price
            std_dev: Rolling standard deviation
            
        Returns:
            Dictionary with extreme detection results
        """
        if std_dev == 0:
            return {
                'is_extreme': False,
                'z_score': 0.0,
                'sigma_level': 0.0,
                'direction': 'none'
            }

        z_score = (current_price - mean_price) / std_dev
        sigma_level = abs(z_score)
        
        return {
            'is_extreme': sigma_level >= 2.0,
            'is_moderate': sigma_level >= 1.0,
            'z_score': z_score,
            'sigma_level': sigma_level,
            'direction': 'above' if z_score > 0 else 'below' if z_score < 0 else 'none',
            'reversion_probability': min(0.95, sigma_level * 0.34 + 0.5)  # Rough approximation
        }

    def get_reversion_targets(self, 
                            current_price: float,
                            mean_price: float,
                            std_dev: float) -> Dict[str, float]:
        """
        Calculate potential reversion target prices.
        
        Args:
            current_price: Current market price
            mean_price: Rolling mean price
            std_dev: Rolling standard deviation
            
        Returns:
            Dictionary with target prices
        """
        return {
            'mean_target': mean_price,
            'conservative_target': mean_price + (0.5 * std_dev * (1 if current_price < mean_price else -1)),
            'aggressive_target': mean_price + (1.0 * std_dev * (1 if current_price < mean_price else -1)),
            'stop_loss': current_price + (0.5 * std_dev * (1 if current_price > mean_price else -1))
        }


def create_mean_reversion_analyzer() -> MeanReversionAnalyzer:
    """Factory function to create analyzer with default settings."""
    return MeanReversionAnalyzer()