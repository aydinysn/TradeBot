import os
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional


load_dotenv()

@dataclass
class TradingConfig:
    
    volume_threshold: float = 500_000    
    oi_change_threshold: float = 0.01    
    interval: str = "1m"
    lookback: int = 10 
    api_delay: float = 0.5   
    leverage: int = 20 
    take_profit_percent: float = 40.0 
    stop_loss_percent: float = 20.0    
    position_duration_min: int = 1      
    position_duration_max: int = 2880    

@dataclass
class StrategyWeights:
    
    funding_rate: float = 0.15
    oi_change: float = 0.15
    volume: float = 0.20
    price_momentum: float = 0.25  
    volatility: float = 0.25      

@dataclass
class AIConfig:
    
    model_name = "gemini-2.5-flash" 
    temperature: float = 0.2  
    confidence_threshold: float = 70.0  
    enabled: bool = True 

class Config:
    
    def __init__(self):
        
        self.binance_api_key = os.getenv("BINANCE_API_KEY", "")
        self.binance_api_secret = os.getenv("BINANCE_API_SECRET", "")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        
        
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        
        
        self.trading = TradingConfig()
        
        
        self.ai = AIConfig()
        
        
        self.strategy_weights = StrategyWeights()
        
        
        self.volatility_threshold = 0.8
        self.btc_dominance_threshold = 0.5
        self.market_cap_change_threshold = 0.05
        
        
        self.short_window = 5    
        self.long_window = 15    
        self.rsi_period = 14
        self.rsi_overbought = 60 
        self.rsi_oversold = 40   
        self.bollinger_period = 20
        self.bollinger_std = 2
        
        
        self.min_funding_rate = 0.0001   
        self.max_funding_rate = -0.0001  
        self.min_funding_time = 1800    
        
    
        self.volume_threshold_advanced = 1_000_000  
        self.oi_threshold_advanced = 0.01           
        self.price_change_threshold = 0.005          


config = Config()
