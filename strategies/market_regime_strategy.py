from typing import Dict, Any, List
from .base_strategy import BaseStrategy, SignalResult
from config import config
import numpy as np

class MarketRegimeStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("MarketRegime")
        self.volatility_threshold = config.volatility_threshold
        self.btc_dominance_threshold = config.btc_dominance_threshold
        self.market_cap_change_threshold = config.market_cap_change_threshold
    
    def get_required_data(self) -> list:
        return ['btc_dominance', 'market_cap_change', 'volatility_index', 'market_data']
    
    def analyze_symbol(self, symbol: str, market_data: Dict[str, Any]) -> SignalResult:
        if not self.validate_data(market_data):
            return SignalResult(
                action='NEUTRAL',
                confidence=0.0,
                reason='Gerekli veriler eksik',
                strategy_name=self.name
            )
        
        # Market regime'i tespit et
        regime = self._detect_market_regime(market_data)
        
        # Regime'e göre strateji ayarları
        adjusted_strategy = self._adjust_strategy_for_regime(regime, market_data)
        
        # Sembol-spesifik analiz
        symbol_analysis = self._analyze_symbol_in_regime(symbol, regime, market_data)
        
        # Final sinyal
        final_signal = self._generate_regime_signal(regime, adjusted_strategy, symbol_analysis)
        
        return final_signal
    
    def _detect_market_regime(self, market_data: Dict[str, Any]) -> str:
        btc_dominance = market_data.get('btc_dominance', 0.5)
        market_cap_change = market_data.get('market_cap_change', 0.0)
        volatility_index = market_data.get('volatility_index', 0.5)
        
        if volatility_index > self.volatility_threshold:
            return 'VOLATILE'
        
        if btc_dominance > self.btc_dominance_threshold and market_cap_change > self.market_cap_change_threshold:
            return 'TRENDING_UP'
        elif btc_dominance < (1 - self.btc_dominance_threshold) and market_cap_change < -self.market_cap_change_threshold:
            return 'TRENDING_DOWN'
        
        return 'SIDEWAYS'
    
    def _adjust_strategy_for_regime(self, regime: str, market_data: Dict[str, Any]) -> Dict[str, Any]:
        base_strategy = {
            'stop_loss': config.trading.stop_loss_percent,
            'take_profit': config.trading.take_profit_percent,
            'position_duration': (config.trading.position_duration_min + config.trading.position_duration_max) / 2,
            'risk_multiplier': 1.0,
            'volume_threshold': config.trading.volume_threshold
        }
        
        if regime == 'VOLATILE':
            base_strategy['stop_loss'] *= 0.7  
            base_strategy['take_profit'] *= 0.8 
            base_strategy['position_duration'] *= 0.6 
            base_strategy['risk_multiplier'] = 0.7
            base_strategy['volume_threshold'] *= 1.5 
            
        elif regime == 'TRENDING_UP':
            base_strategy['stop_loss'] *= 1.2 
            base_strategy['take_profit'] *= 1.3 
            base_strategy['position_duration'] *= 1.5 
            base_strategy['risk_multiplier'] = 1.2
            base_strategy['volume_threshold'] *= 0.8 
            
        elif regime == 'TRENDING_DOWN':
            base_strategy['stop_loss'] *= 0.8 
            base_strategy['take_profit'] *= 0.9 
            base_strategy['position_duration'] *= 0.7 
            base_strategy['risk_multiplier'] = 0.8
            base_strategy['volume_threshold'] *= 1.2 
            
        else:  # SIDEWAYS
            base_strategy['stop_loss'] *= 1.0 
            base_strategy['take_profit'] *= 1.0 
            base_strategy['position_duration'] *= 1.0 
            base_strategy['risk_multiplier'] = 1.0
            base_strategy['volume_threshold'] *= 1.0 
        
        return base_strategy
    
    def _analyze_symbol_in_regime(self, symbol: str, regime: str, market_data: Dict[str, Any]) -> Dict[str, Any]:
        symbol_data = market_data.get('market_data', {}).get(symbol, {})
        
        if not symbol_data:
            return {'signal': 'NEUTRAL', 'confidence': 0.0, 'reason': 'Sembol verisi yok'}
        
        if regime == 'VOLATILE':
            volume_score = self._score_volume_volatility(symbol_data)
            momentum_score = self._score_momentum_volatility(symbol_data)
            total_score = (volume_score + momentum_score) / 2
            
        elif regime == 'TRENDING_UP':
            trend_score = self._score_trend_strength(symbol_data, 'UP')
            volume_score = self._score_volume_trend(symbol_data)
            total_score = (trend_score * 0.7 + volume_score * 0.3)
            
        elif regime == 'TRENDING_DOWN':
            trend_score = self._score_trend_strength(symbol_data, 'DOWN')
            volume_score = self._score_volume_trend(symbol_data)
            total_score = (trend_score * 0.7 + volume_score * 0.3)
            
        else:   
            mean_rev_score = self._score_mean_reversion(symbol_data)
            volume_score = self._score_volume_sideways(symbol_data)
            total_score = (mean_rev_score * 0.6 + volume_score * 0.4)
        
        if regime in ['TRENDING_UP', 'TRENDING_DOWN']:
            action = 'LONG' if regime == 'TRENDING_UP' else 'SHORT'
        else:
            action = 'NEUTRAL'
        
        return {
            'signal': action,
            'confidence': total_score,
            'reason': f'{regime} regime - Skor: {total_score:.2f}'
        }
    
    def _score_volume_volatility(self, symbol_data: Dict[str, Any]) -> float:
        current_volume = symbol_data.get('volume', 0)
        avg_volume = symbol_data.get('avg_volume', current_volume)
        
        if avg_volume == 0:
            return 0.0
        
        volume_ratio = current_volume / avg_volume
        return min(1.0, volume_ratio / 3.0)  
    
    def _score_momentum_volatility(self, symbol_data: Dict[str, Any]) -> float:
        price_change = abs(symbol_data.get('price_change', 0))
        return min(1.0, price_change / 0.1) 
    
    def _score_trend_strength(self, symbol_data: Dict[str, Any], direction: str) -> float:
        short_ma = symbol_data.get('short_ma', 0)
        long_ma = symbol_data.get('long_ma', 0)
        current_price = symbol_data.get('current_price', 0)
        
        if long_ma == 0:
            return 0.0
        
        if direction == 'UP':
            trend_aligned = short_ma > long_ma and current_price > short_ma
        else:
            trend_aligned = short_ma < long_ma and current_price < short_ma
        
        if not trend_aligned:
            return 0.0
        
        trend_strength = abs(short_ma - long_ma) / long_ma
        return min(1.0, trend_strength * 50)  
    
    def _score_volume_trend(self, symbol_data: Dict[str, Any]) -> float:
        current_volume = symbol_data.get('volume', 0)
        avg_volume = symbol_data.get('avg_volume', current_volume)
        
        if avg_volume == 0:
            return 0.0
        
        volume_ratio = current_volume / avg_volume
        return min(1.0, volume_ratio / 2.0)  
    
    def _score_mean_reversion(self, symbol_data: Dict[str, Any]) -> float:
        rsi = symbol_data.get('rsi', 50)
        bb_position = symbol_data.get('bb_position', 0.5)  
        
        rsi_score = 0.0
        if rsi < 30 or rsi > 70:
            rsi_score = 1.0 - (abs(rsi - 50) / 50) 
        
        
        bb_score = 0.0
        if bb_position < 0.2 or bb_position > 0.8:
            bb_score = 1.0 - min(bb_position, 1 - bb_position) * 2  
        
        return (rsi_score + bb_score) / 2
    
    def _score_volume_sideways(self, symbol_data: Dict[str, Any]) -> float:
        current_volume = symbol_data.get('volume', 0)
        avg_volume = symbol_data.get('avg_volume', current_volume)
        
        if avg_volume == 0:
            return 0.0
        
        volume_ratio = current_volume / avg_volume
        if 0.8 <= volume_ratio <= 1.5:
            return 1.0
        elif volume_ratio < 0.8:
            return volume_ratio / 0.8
        else:
            return max(0, 2.0 - volume_ratio / 1.5)
    
    def _generate_regime_signal(self, regime: str, adjusted_strategy: Dict[str, Any], symbol_analysis: Dict[str, Any]) -> SignalResult:
        if symbol_analysis['confidence'] < 0.3:
            action = 'NEUTRAL'
            confidence = 0.0
            reason = f'{regime} regime - Düşük güvenilirlik'
        else:
            action = symbol_analysis['signal']
            confidence = symbol_analysis['confidence']
            reason = symbol_analysis['reason']
        
        metadata = {
            'market_regime': regime,
            'adjusted_strategy': adjusted_strategy,
            'symbol_analysis': symbol_analysis,
            'regime_characteristics': self._get_regime_characteristics(regime)
        }
        
        return SignalResult(
            action=action,
            confidence=confidence,
            reason=reason,
            strategy_name=self.name,
            metadata=metadata
        )
    
    def _get_regime_characteristics(self, regime: str) -> Dict[str, Any]:
        characteristics = {
            'VOLATILE': {
                'description': 'Yüksek volatilite, sıkı risk yönetimi gerekli',
                'recommended_actions': ['Kısa pozisyonlar', 'Sıkı stop-loss', 'Düşük kaldıraç'],
                'risk_level': 'YÜKSEK'
            },
            'TRENDING_UP': {
                'description': 'Yükselen trend, agresif long pozisyonlar',
                'recommended_actions': ['Long pozisyonlar', 'Trend following', 'Yüksek kaldıraç'],
                'risk_level': 'ORTA'
            },
            'TRENDING_DOWN': {
                'description': 'Düşen trend, muhafazakar short pozisyonlar',
                'recommended_actions': ['Short pozisyonlar', 'Trend following', 'Orta kaldıraç'],
                'risk_level': 'ORTA'
            },
            'SIDEWAYS': {
                'description': 'Yatay piyasa, mean reversion stratejileri',
                'recommended_actions': ['Range trading', 'Mean reversion', 'Düşük kaldıraç'],
                'risk_level': 'DÜŞÜK'
            }
        }
        
        return characteristics.get(regime, {})
