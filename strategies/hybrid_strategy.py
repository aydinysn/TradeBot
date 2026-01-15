from typing import Dict, Any, List
from .base_strategy import BaseStrategy, SignalResult
from config import config
import numpy as np

class HybridStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("Hybrid")
        self.short_window = config.short_window
        self.long_window = config.long_window
        self.rsi_period = config.rsi_period
        self.rsi_overbought = config.rsi_overbought
        self.rsi_oversold = config.rsi_oversold
        self.bollinger_period = config.bollinger_period
        self.bollinger_std = config.bollinger_std
    
    def get_required_data(self) -> list:
        return ['price_history', 'volume_history']
    
    def analyze_symbol(self, symbol: str, market_data: Dict[str, Any]) -> SignalResult:
        if not self.validate_data(market_data):
            return SignalResult(
                action='NEUTRAL',
                confidence=0.0,
                reason='Gerekli veriler eksik',
                strategy_name=self.name
            )
        
        price_history = market_data['price_history']
        volume_history = market_data['volume_history']
        
        if len(price_history) < max(self.long_window, self.bollinger_period):
            return SignalResult(
                action='NEUTRAL',
                confidence=0.0,
                reason='Yeterli fiyat verisi yok',
                strategy_name=self.name
            )
        
        short_ma = self._calculate_sma(price_history, self.short_window)
        long_ma = self._calculate_sma(price_history, self.long_window)
        rsi = self._calculate_rsi(price_history, self.rsi_period)
        bb_upper, bb_lower = self._calculate_bollinger_bands(price_history, self.bollinger_period, self.bollinger_std)
        
        current_price = price_history[-1]
        current_volume = volume_history[-1]
        avg_volume = np.mean(volume_history[-20:])  
        
        trend_strength = self._analyze_trend(short_ma, long_ma, current_price)
        
        mean_reversion_signal = self._analyze_mean_reversion(
            current_price, rsi, bb_upper, bb_lower
        )
        
        volume_signal = self._analyze_volume(current_volume, avg_volume)
        
        signal = self._consolidate_signals(
            trend_strength, mean_reversion_signal, volume_signal
        )
        
        return signal
    
    def _calculate_sma(self, prices: List[float], window: int) -> float:
        if len(prices) < window:
            return prices[-1] if prices else 0.0
        return np.mean(prices[-window:])
    
    def _calculate_rsi(self, prices: List[float], period: int) -> float:
        if len(prices) < period + 1:
            return 50.0 
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gains = np.mean(gains[-period:])
        avg_losses = np.mean(losses[-period:])
        
        if avg_losses == 0:
            return 100.0
        
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_bollinger_bands(self, prices: List[float], period: int, std_dev: float) -> tuple:
        if len(prices) < period:
            current_price = prices[-1] if prices else 0.0
            return current_price * 1.02, current_price * 0.98
        
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        return upper_band, lower_band
    
    def _analyze_trend(self, short_ma: float, long_ma: float, current_price: float) -> Dict[str, Any]:
        trend_direction = 'UP' if short_ma > long_ma else 'DOWN'
        trend_strength = abs(short_ma - long_ma) / long_ma
        
        normalized_strength = min(1.0, trend_strength * 100)
        
        price_trend_aligned = (
            (trend_direction == 'UP' and current_price > short_ma) or
            (trend_direction == 'DOWN' and current_price < short_ma)
        )
        
        return {
            'direction': trend_direction,
            'strength': normalized_strength,
            'aligned': price_trend_aligned
        }
    
    def _analyze_mean_reversion(self, current_price: float, rsi: float, bb_upper: float, bb_lower: float) -> Dict[str, Any]:
        rsi_extreme = False
        rsi_signal = None
        
        if rsi < self.rsi_oversold:
            rsi_extreme = True
            rsi_signal = 'LONG'
        elif rsi > self.rsi_overbought:
            rsi_extreme = True
            rsi_signal = 'SHORT'
        
        bb_extreme = False
        bb_signal = None
        
        if current_price < bb_lower * 0.99:  
            bb_extreme = True
            bb_signal = 'LONG'
        elif current_price > bb_upper * 1.01:  
            bb_extreme = True
            bb_signal = 'SHORT'
        
        if rsi_extreme and bb_extreme and rsi_signal == bb_signal:
            strength = 1.0 
        elif rsi_extreme or bb_extreme:
            strength = 0.7 
        else:
            strength = 0.0
        
        return {
            'rsi_extreme': rsi_extreme,
            'rsi_signal': rsi_signal,
            'bb_extreme': bb_extreme,
            'bb_signal': bb_signal,
            'strength': strength,
            'signal': rsi_signal if rsi_signal == bb_signal else None
        }
    
    def _analyze_volume(self, current_volume: float, avg_volume: float) -> Dict[str, Any]:
        if avg_volume == 0:
            return {'ratio': 1.0, 'signal': 'NEUTRAL'}
        
        volume_ratio = current_volume / avg_volume
        
        if volume_ratio > 2.0:
            signal = 'HIGH'
        elif volume_ratio > 1.5:
            signal = 'MEDIUM'
        else:
            signal = 'LOW'
        
        return {
            'ratio': volume_ratio,
            'signal': signal
        }
    
    def _consolidate_signals(self, trend: Dict, mean_rev: Dict, volume: Dict) -> SignalResult:
        if trend['aligned'] and trend['strength'] > 0.3:
            if trend['direction'] == 'UP':
                trend_signal = 'LONG'
                trend_confidence = trend['strength']
            else:
                trend_signal = 'SHORT'
                trend_confidence = trend['strength']
        else:
            trend_signal = 'NEUTRAL'
            trend_confidence = 0.0
        
        mean_rev_signal = mean_rev['signal']
        mean_rev_confidence = mean_rev['strength']
        
        volume_bonus = 0.0
        if volume['signal'] == 'HIGH':
            volume_bonus = 0.2
        elif volume['signal'] == 'MEDIUM':
            volume_bonus = 0.1
        
        if trend_signal != 'NEUTRAL' and mean_rev_signal == trend_signal:
            action = trend_signal
            confidence = min(1.0, (trend_confidence + mean_rev_confidence) / 2 + volume_bonus)
            reason = f"Trend + Mean Reversion uyumlu - {trend_signal}"
        elif trend_signal != 'NEUTRAL' and mean_rev_signal is None:
            action = trend_signal
            confidence = min(1.0, trend_confidence * 0.8 + volume_bonus)
            reason = f"Trend following - {trend_signal}"
            action = trend_signal
            confidence = min(1.0, trend_confidence * 0.8 + volume_bonus)
            reason = f"Trend following - {trend_signal}"
        elif mean_rev_signal is not None and trend_signal == 'NEUTRAL':
            action = mean_rev_signal
            confidence = min(1.0, mean_rev_confidence * 0.8 + volume_bonus)
            reason = f"Mean Reversion - {mean_rev_signal}"
        else:
            action = 'NEUTRAL'
            confidence = 0.0
            reason = 'Çelişkili sinyaller'
        
        metadata = {
            'trend_direction': trend['direction'],
            'trend_strength': trend['strength'],
            'trend_aligned': trend['aligned'],
            'mean_reversion_strength': mean_rev['strength'],
            'volume_ratio': volume['ratio'],
            'volume_signal': volume['signal']
        }
        
        return SignalResult(
            action=action,
            confidence=confidence,
            reason=reason,
            strategy_name=self.name,
            metadata=metadata
        )
