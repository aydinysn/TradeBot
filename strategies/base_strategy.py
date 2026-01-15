from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class SignalResult:
    action: str 
    confidence: float 
    reason: str
    strategy_name: str
    metadata: Optional[Dict[str, Any]] = None

class BaseStrategy(ABC):
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def analyze_symbol(self, symbol: str, market_data: Dict[str, Any]) -> SignalResult:
        pass
    
    @abstractmethod
    def get_required_data(self) -> list:
        pass
    
    def validate_data(self, market_data: Dict[str, Any]) -> bool:
        required_data = self.get_required_data()
        return all(key in market_data for key in required_data)
    
    def get_strategy_info(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.__doc__ or 'No description available',
            'required_data': self.get_required_data()
        }
