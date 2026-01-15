from typing import Dict, Any, List, Optional
from .base_strategy import BaseStrategy, SignalResult
from .multi_factor_strategy import MultiFactorStrategy
from .hybrid_strategy import HybridStrategy
from .market_regime_strategy import MarketRegimeStrategy
from .net_order_flow_strategy import NetOrderFlowStrategy
import logging

logger = logging.getLogger(__name__)

class StrategyManager:
    def __init__(self):
        self.strategies: List[BaseStrategy] = [
            MultiFactorStrategy(),
            HybridStrategy(),
            MarketRegimeStrategy(),
            NetOrderFlowStrategy()
        ]
        
        self.strategy_weights = {
            'MultiFactor': 0.3,
            'Hybrid': 0.25,
            'MarketRegime': 0.2,
            'NetOrderFlow': 0.25
        }
        
        logger.info(f"Strategy Manager başlatıldı. {len(self.strategies)} strateji yüklendi.")
    
    def get_all_strategies(self) -> List[BaseStrategy]:
        return self.strategies
    
    def get_strategy_by_name(self, name: str) -> Optional[BaseStrategy]:
        for strategy in self.strategies:
            if strategy.name == name:
                return strategy
        return None
    
    def analyze_symbol_all_strategies(self, symbol: str, market_data: Dict[str, Any]) -> Dict[str, SignalResult]:
        results = {}
        
        for strategy in self.strategies:
            try:
                result = strategy.analyze_symbol(symbol, market_data)
                results[strategy.name] = result
                logger.debug(f"{symbol} - {strategy.name}: {result.action} ({result.confidence:.2f})")
            except Exception as e:
                logger.error(f"{symbol} - {strategy.name} analizi başarısız: {e}")
              
                results[strategy.name] = SignalResult(
                    action='NEUTRAL',
                    confidence=0.0,
                    reason=f'Hata: {e}',
                    strategy_name=strategy.name
                )
        
        return results
    
    def get_consolidated_signal(self, symbol: str, market_data: Dict[str, Any]) -> SignalResult:
        strategy_results = self.analyze_symbol_all_strategies(symbol, market_data)
        
        if not strategy_results:
            return SignalResult(
                action='NEUTRAL',
                confidence=0.0,
                reason='Hiçbir strateji çalışmadı',
                strategy_name='StrategyManager'
            )
        
        long_votes = 0.0
        short_votes = 0.0
        total_confidence = 0.0
        
        for strategy_name, result in strategy_results.items():
            weight = self.strategy_weights.get(strategy_name, 0.1)
            confidence = result.confidence * weight
            
            if result.action == 'LONG':
                long_votes += confidence
            elif result.action == 'SHORT':
                short_votes += confidence
            
            total_confidence += confidence
        
        if long_votes > short_votes and long_votes > 0.3:
            action = 'LONG'
            confidence = long_votes / total_confidence if total_confidence > 0 else 0.0
            reason = f'Long ağırlıklı oy: {long_votes:.2f} vs {short_votes:.2f}'
            logger.debug(f"[LONG] Sinyali üretildi - Güven: {confidence:.2f} - Sebep: {reason}")
        elif short_votes > long_votes and short_votes > 0.3:
            action = 'SHORT'
            confidence = short_votes / total_confidence if total_confidence > 0 else 0.0
            reason = f'Short ağırlıklı oy: {short_votes:.2f} vs {long_votes:.2f}'
            logger.debug(f"[SHORT] Sinyali üretildi - Güven: {confidence:.2f} - Sebep: {reason}")
        else:
            action = 'NEUTRAL'
            confidence = 0.0
            reason = f'Belirsiz oy: Long {long_votes:.2f}, Short {short_votes:.2f}'
            logger.debug(f"[NEUTRAL] Sinyal - Sebep: {reason}")
        
        if confidence > 0.8:
            strength = "Güçlü"
        elif confidence > 0.6:
            strength = "Orta"
        elif confidence > 0.4:
            strength = "Zayıf"
        else:
            strength = "Çok Zayıf"
        
        final_reason = f"{strength} sinyal - {reason}"
        
        metadata = {
            'strategy_results': strategy_results,
            'long_votes': long_votes,
            'short_votes': short_votes,
            'total_confidence': total_confidence,
            'signal_strength': strength,
            'consensus_level': self._calculate_consensus_level(strategy_results)
        }
        
        return SignalResult(
            action=action,
            confidence=confidence,
            reason=final_reason,
            strategy_name='StrategyManager',
            metadata=metadata
        )
    
    def _calculate_consensus_level(self, strategy_results: Dict[str, SignalResult]) -> float:
        if not strategy_results:
            return 0.0
        
        actions = [result.action for result in strategy_results.values()]
        
        from collections import Counter
        action_counts = Counter(actions)
        most_common_action = action_counts.most_common(1)[0][0]
        most_common_count = action_counts[most_common_action]
        
        consensus = most_common_count / len(actions)
        
        return consensus
    
    def get_strategy_performance_summary(self) -> Dict[str, Any]:
        summary = {
            'total_strategies': len(self.strategies),
            'strategy_names': [s.name for s in self.strategies],
            'strategy_weights': self.strategy_weights,
            'strategy_info': {}
        }
        
        for strategy in self.strategies:
            summary['strategy_info'][strategy.name] = strategy.get_strategy_info()
        
        return summary
    
    def update_strategy_weights(self, new_weights: Dict[str, float]):
        total_weight = sum(new_weights.values())
        if total_weight > 0:
            normalized_weights = {k: v/total_weight for k, v in new_weights.items()}
            self.strategy_weights.update(normalized_weights)
            logger.info(f"Strateji ağırlıkları güncellendi: {self.strategy_weights}")
        else:
            logger.warning("Geçersiz ağırlık değerleri, güncelleme yapılmadı")
    
    def get_best_strategy_for_symbol(self, symbol: str, market_data: Dict[str, Any]) -> Optional[BaseStrategy]:
        strategy_results = self.analyze_symbol_all_strategies(symbol, market_data)
        
        if not strategy_results:
            return None
        
        best_strategy = max(strategy_results.items(), key=lambda x: x[1].confidence)
        
        return self.get_strategy_by_name(best_strategy[0])
    
    def validate_market_data(self, market_data: Dict[str, Any]) -> Dict[str, bool]:
        validation_results = {}
        
        for strategy in self.strategies:
            is_valid = strategy.validate_data(market_data)
            validation_results[strategy.name] = is_valid
            
            if not is_valid:
                missing_data = set(strategy.get_required_data()) - set(market_data.keys())
                logger.warning(f"{strategy.name} için eksik veriler: {missing_data}")
        
        return validation_results
