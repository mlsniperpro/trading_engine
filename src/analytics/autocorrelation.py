"""
Autocorrelation Analytics Module

Calculates price serial correlation to identify market regimes:
- Trending vs Mean-reverting regimes
- Momentum persistence measurement
- Statistical significance testing

Supports the AutocorrelationFilter in the decision engine.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
try:
    from scipy import stats
except ImportError:
    print("Warning: scipy not installed. Statistical tests will be simplified.")
    stats = None

logger = logging.getLogger(__name__)


@dataclass
class AutocorrelationMetrics:
    """Container for autocorrelation analytics results."""
    price_autocorrelation: float
    return_autocorrelation: float
    lag1_correlation: float
    lag5_correlation: float
    significance_level: float
    regime: str  # 'trending', 'mean_reverting', 'random_walk', 'mixed'
    momentum_strength: float
    persistence_score: float


class AutocorrelationAnalyzer:
    """
    Analyzes price time series for autocorrelation patterns.
    
    Autocorrelation measures how much current price movements 
    depend on past price movements, helping identify:
    - Trending markets (high positive correlation)
    - Mean-reverting markets (negative correlation)
    - Random walk markets (near-zero correlation)
    """

    def __init__(self, 
                 lookback_periods: int = 50,
                 max_lags: int = 10,
                 significance_threshold: float = 0.05):
        """
        Initialize autocorrelation analyzer.
        
        Args:
            lookback_periods: Number of periods to analyze
            max_lags: Maximum lag periods to calculate
            significance_threshold: P-value threshold for significance
        """
        self.lookback_periods = lookback_periods
        self.max_lags = max_lags
        self.significance_threshold = significance_threshold
        logger.info(f"AutocorrelationAnalyzer initialized (lookback={lookback_periods}, lags={max_lags})")

    def analyze(self, price_data: List[Dict[str, Any]]) -> Optional[AutocorrelationMetrics]:
        """
        Analyze price data for autocorrelation patterns.
        
        Args:
            price_data: List of price records with timestamp and price
            
        Returns:
            AutocorrelationMetrics or None if insufficient data
        """
        try:
            if len(price_data) < self.lookback_periods:
                logger.warning(f"Insufficient data: {len(price_data)} < {self.lookback_periods}")
                return None

            # Convert to pandas and calculate returns
            df = pd.DataFrame(price_data)
            if 'price' not in df.columns:
                logger.error("Price column missing from data")
                return None

            prices = df['price'].astype(float).tail(self.lookback_periods)
            returns = prices.pct_change().dropna()

            if len(returns) < 20:  # Minimum for meaningful analysis
                logger.warning("Insufficient return data for analysis")
                return None

            # Calculate price level autocorrelation (lag-1)
            price_autocorr = self._calculate_autocorrelation(prices.values, lag=1)
            
            # Calculate return autocorrelation (more statistically meaningful)
            return_autocorr = self._calculate_autocorrelation(returns.values, lag=1)
            
            # Calculate specific lag correlations
            lag1_corr = return_autocorr
            lag5_corr = self._calculate_autocorrelation(returns.values, lag=5)

            # Test statistical significance
            significance_level = self._test_significance(returns.values, lag1_corr)

            # Determine market regime
            regime = self._classify_regime(return_autocorr, significance_level)
            
            # Calculate momentum and persistence metrics
            momentum_strength = self._calculate_momentum_strength(returns.values)
            persistence_score = self._calculate_persistence_score(returns.values)

            return AutocorrelationMetrics(
                price_autocorrelation=float(price_autocorr),
                return_autocorrelation=float(return_autocorr),
                lag1_correlation=float(lag1_corr),
                lag5_correlation=float(lag5_corr),
                significance_level=float(significance_level),
                regime=regime,
                momentum_strength=float(momentum_strength),
                persistence_score=float(persistence_score)
            )

        except Exception as e:
            logger.error(f"Error in autocorrelation analysis: {e}")
            return None

    def _calculate_autocorrelation(self, data: np.ndarray, lag: int = 1) -> float:
        """
        Calculate autocorrelation at specified lag.
        
        Args:
            data: Time series data
            lag: Lag period
            
        Returns:
            Autocorrelation coefficient
        """
        if len(data) <= lag:
            return 0.0
            
        try:
            # Remove any NaN values
            clean_data = data[~np.isnan(data)]
            
            if len(clean_data) <= lag:
                return 0.0
                
            # Calculate Pearson correlation between data and lagged data
            x = clean_data[:-lag]
            y = clean_data[lag:]
            
            if len(x) == 0 or np.std(x) == 0 or np.std(y) == 0:
                return 0.0
                
            correlation = np.corrcoef(x, y)[0, 1]
            return correlation if not np.isnan(correlation) else 0.0
            
        except Exception:
            return 0.0

    def _test_significance(self, returns: np.ndarray, correlation: float) -> float:
        """
        Test statistical significance of autocorrelation.
        
        Args:
            returns: Return series
            correlation: Autocorrelation coefficient
            
        Returns:
            P-value of significance test
        """
        try:
            n = len(returns)
            # Standard error under null hypothesis
            se = 1.0 / np.sqrt(n)
            # Test statistic
            t_stat = correlation / se
            
            # Two-tailed p-value
            if stats is not None:
                p_value = 2 * (1 - stats.norm.cdf(abs(t_stat)))
            else:
                # Simplified approximation when scipy not available
                # Using normal distribution approximation
                import math
                z_score = abs(t_stat)
                # Rough approximation: p = 2 * (1 - Φ(|z|))
                p_value = 2 * (1 - 0.5 * (1 + math.erf(z_score / math.sqrt(2))))
            
            return float(p_value)
        except Exception:
            return 1.0  # Not significant

    def _classify_regime(self, correlation: float, p_value: float) -> str:
        """
        Classify market regime based on autocorrelation.
        
        Args:
            correlation: Autocorrelation coefficient
            p_value: Statistical significance
            
        Returns:
            Regime classification string
        """
        # Check if statistically significant
        if p_value > self.significance_threshold:
            return 'random_walk'
        
        abs_corr = abs(correlation)
        
        if abs_corr > 0.6:
            return 'trending' if correlation > 0 else 'mean_reverting'
        elif abs_corr > 0.3:
            return 'mixed'
        else:
            return 'random_walk'

    def _calculate_momentum_strength(self, returns: np.ndarray) -> float:
        """
        Calculate momentum strength measure.
        
        Args:
            returns: Return series
            
        Returns:
            Momentum strength score [0, 1]
        """
        try:
            if len(returns) < 10:
                return 0.0
                
            # Calculate rolling correlations at different lags
            correlations = []
            for lag in range(1, min(6, len(returns) // 4)):
                corr = self._calculate_autocorrelation(returns, lag)
                if not np.isnan(corr):
                    correlations.append(abs(corr))
            
            if not correlations:
                return 0.0
                
            # Average absolute correlation as momentum strength
            strength = np.mean(correlations)
            return min(1.0, strength)
            
        except Exception:
            return 0.0

    def _calculate_persistence_score(self, returns: np.ndarray) -> float:
        """
        Calculate persistence score based on run lengths.
        
        Args:
            returns: Return series
            
        Returns:
            Persistence score [0, 1]
        """
        try:
            if len(returns) < 10:
                return 0.0
                
            # Calculate signs of returns
            signs = np.sign(returns[returns != 0])
            
            if len(signs) < 5:
                return 0.0
                
            # Calculate run lengths (consecutive same signs)
            runs = []
            current_run = 1
            
            for i in range(1, len(signs)):
                if signs[i] == signs[i-1]:
                    current_run += 1
                else:
                    runs.append(current_run)
                    current_run = 1
            runs.append(current_run)
            
            # Persistence = average run length normalized
            avg_run_length = np.mean(runs)
            # Normalize by expected run length for random series (≈2)
            persistence = (avg_run_length - 1) / len(signs)
            return min(1.0, max(0.0, persistence))
            
        except Exception:
            return 0.0

    def get_correlation_matrix(self, price_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Generate full autocorrelation matrix for detailed analysis.
        
        Args:
            price_data: List of price records
            
        Returns:
            Dictionary with correlation matrix and statistics
        """
        try:
            if len(price_data) < self.lookback_periods:
                return None
                
            df = pd.DataFrame(price_data)
            prices = df['price'].astype(float).tail(self.lookback_periods)
            returns = prices.pct_change().dropna()
            
            if len(returns) < 20:
                return None
                
            # Calculate autocorrelations for multiple lags
            correlations = {}
            p_values = {}
            
            for lag in range(1, min(self.max_lags + 1, len(returns) // 4)):
                corr = self._calculate_autocorrelation(returns.values, lag)
                p_val = self._test_significance(returns.values, corr)
                
                correlations[f'lag_{lag}'] = float(corr)
                p_values[f'lag_{lag}'] = float(p_val)
            
            return {
                'correlations': correlations,
                'p_values': p_values,
                'data_points': len(returns),
                'significance_threshold': self.significance_threshold
            }
            
        except Exception as e:
            logger.error(f"Error generating correlation matrix: {e}")
            return None


def create_autocorrelation_analyzer() -> AutocorrelationAnalyzer:
    """Factory function to create analyzer with default settings."""
    return AutocorrelationAnalyzer()