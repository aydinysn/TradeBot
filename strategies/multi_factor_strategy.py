from typing import Dict, Any
from .base_strategy import BaseStrategy, SignalResult
from config import config

class MultiFactorStrategy(BaseStrategy):
    """Multi-factor scoring stratejisi - Mevcut stratejiyi geliştirir"""
    
    def __init__(self):
        super().__init__("MultiFactor")
        self.weights = config.strategy_weights
    
    def get_required_data(self) -> list:
        return ['funding_rate', 'oi_change', 'volume', 'price_change', 'volatility']
    
    def analyze_symbol(self, symbol: str, market_data: Dict[str, Any]) -> SignalResult:
        """Multi-factor scoring ile sembol analizi"""
        if not self.validate_data(market_data):
            return SignalResult(
                action='NEUTRAL',
                confidence=0.0,
                reason='Gerekli veriler eksik',
                strategy_name=self.name
            )
        
        # Her faktör için puan hesapla
        funding_score = self._score_funding_rate(market_data['funding_rate'])
        oi_score = self._score_oi_change(market_data['oi_change'])
        volume_score = self._score_volume(market_data['volume'])
        momentum_score = self._score_momentum(market_data['price_change'])
        volatility_score = self._score_volatility(market_data['volatility'])
        
        # Ağırlıklı toplam puan
        total_score = (
            funding_score * self.weights.funding_rate +
            oi_score * self.weights.oi_change +
            volume_score * self.weights.volume +
            momentum_score * self.weights.price_momentum +
            volatility_score * self.weights.volatility
        )
        
        # Pozisyon yönü belirleme
        if market_data['funding_rate'] < 0 and market_data['oi_change'] > 0:
            action = 'LONG'
            direction_bonus = 0.1
        elif market_data['funding_rate'] > 0 and market_data['oi_change'] > 0:
            action = 'SHORT'
            direction_bonus = 0.1
        else:
            action = 'NEUTRAL'
            direction_bonus = 0.0
        
        # Güvenilirlik hesaplama
        confidence = min(1.0, total_score + direction_bonus)
        
        # Sinyal gücü belirleme
        if confidence > 0.8:
            strength = "Güçlü"
        elif confidence > 0.6:
            strength = "Orta"
        else:
            strength = "Zayıf"
        
        reason = f"{strength} sinyal - Toplam puan: {total_score:.2f}"
        
        metadata = {
            'funding_score': funding_score,
            'oi_score': oi_score,
            'volume_score': volume_score,
            'momentum_score': momentum_score,
            'volatility_score': volatility_score,
            'total_score': total_score,
            'signal_strength': strength
        }
        
        return SignalResult(
            action=action,
            confidence=confidence,
            reason=reason,
            strategy_name=self.name,
            metadata=metadata
        )
    
    def _score_funding_rate(self, funding_rate: float) -> float:
        """Funding rate için puan hesaplama"""
        # Funding rate mutlak değeri ne kadar yüksekse o kadar iyi
        # -0.01 = 100 puan, 0.01 = 100 puan, 0 = 0 puan
        return min(100, abs(funding_rate) * 10000)
    
    def _score_oi_change(self, oi_change: float) -> float:
        """OI değişimi için puan hesaplama"""
        # OI değişimi ne kadar yüksekse o kadar iyi
        # %10+ = 100 puan, %0 = 0 puan
        return min(100, abs(oi_change) * 1000)
    
    def _score_volume(self, volume: float) -> float:
        """Hacim için puan hesaplama"""
        # Hacim threshold'u aşan kısım için puan
        threshold = config.trading.volume_threshold
        if volume <= threshold:
            return 0.0
        
        # Threshold'u aşan her 1M USD için 10 puan
        excess_volume = volume - threshold
        score = min(100, (excess_volume / 1_000_000) * 10)
        return score
    
    def _score_momentum(self, price_change: float) -> float:
        """Fiyat momentumu için puan hesaplama"""
        # Fiyat değişimi ne kadar yüksekse o kadar iyi
        # %5+ = 100 puan, %0 = 0 puan
        return min(100, abs(price_change) * 20)
    
    def _score_volatility(self, volatility: float) -> float:
        """Volatilite için puan hesaplama"""
        # Orta volatilite en iyi (çok düşük veya çok yüksek değil)
        # %2-5 arası = 100 puan
        if 0.02 <= volatility <= 0.05:
            return 100.0
        elif volatility < 0.02:
            # Düşük volatilite için azalan puan
            return max(0, volatility * 5000)
        else:
            # Yüksek volatilite için azalan puan
            return max(0, 100 - (volatility - 0.05) * 2000)
