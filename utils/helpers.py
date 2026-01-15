import time
import logging
from typing import Optional, Dict, Any
from functools import lru_cache
import requests

# Logging ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def safe_api_call(func, *args, **kwargs) -> Optional[Any]:
    """API çağrılarını güvenli şekilde yapar"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"API çağrısı başarısız: {func.__name__} - {e}")
        return None

def rate_limit_delay(delay: float = 0.25):
    """Rate limiting için gecikme"""
    time.sleep(delay)

@lru_cache(maxsize=1)
def load_futures_exchange_info() -> Dict[str, Any]:
    """Futures exchange bilgilerini cache'ler"""
    try:
        r = requests.get("https://fapi.binance.com/fapi/v1/exchangeInfo", timeout=10)
        return r.json() if r.status_code == 200 else {}
    except Exception as e:
        logger.error(f"Exchange info yüklenemedi: {e}")
        return {}

def get_futures_filters(symbol_id: str) -> Dict[str, Optional[float]]:
    """Sembol için futures filtrelerini getirir"""
    info = load_futures_exchange_info()
    result = {
        'minQty': None, 
        'stepSize': None, 
        'marketMinQty': None, 
        'marketStepSize': None, 
        'minNotional': None
    }
    
    try:
        symbols = info.get('symbols', [])
        for s in symbols:
            if s.get('symbol') == symbol_id:
                for f in s.get('filters', []):
                    if f.get('filterType') == 'LOT_SIZE':
                        result['minQty'] = float(f.get('minQty'))
                        result['stepSize'] = float(f.get('stepSize'))
                    elif f.get('filterType') == 'MARKET_LOT_SIZE':
                        result['marketMinQty'] = float(f.get('minQty'))
                        result['marketStepSize'] = float(f.get('stepSize'))
                    elif f.get('filterType') in ('MIN_NOTIONAL', 'MIN_NOTIONAL'):
                        val = f.get('notional') or f.get('minNotional')
                        if val is not None:
                            result['minNotional'] = float(val)
                break
    except Exception as e:
        logger.error(f"Futures filtreleri alınamadı: {e}")
    
    return result

def to_futures_symbol(symbol: str) -> str:
    """Sembol formatını futures formatına çevirir"""
    if '/' in symbol:
        base, quote = symbol.split('/')
        return f"{base}/{quote}" if quote.upper() == 'USDT' else symbol
    if symbol.upper().endswith('USDT'):
        base = symbol[:-4]
        return f"{base}/USDT"
    return symbol

def format_number(number: float, decimals: int = 4) -> str:
    """Sayıyı formatlar"""
    return f"{number:.{decimals}f}"

def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """Yüzde değişimi hesaplar"""
    if old_value == 0:
        return 0.0
    return ((new_value - old_value) / old_value) * 100

def is_valid_symbol(symbol: str) -> bool:
    """Sembol geçerli mi kontrol eder"""
    return symbol and len(symbol) > 0 and 'USDT' in symbol.upper()
