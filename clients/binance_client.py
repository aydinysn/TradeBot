import ccxt
import time
import logging
from typing import Dict, Any, Optional, List
from config import config
from utils.helpers import safe_api_call, rate_limit_delay

logger = logging.getLogger(__name__)

class BinanceClient:
    def __init__(self):
        self.api_key = config.binance_api_key
        self.api_secret = config.binance_api_secret
        self.leverage = config.trading.leverage
        
        if not self.api_key or not self.api_secret:
            logger.error("Binance API anahtarları eksik! Lütfen .env dosyasını kontrol edin.")
            raise ValueError("Binance API anahtarları eksik (BINANCE_API_KEY, BINANCE_API_SECRET)")

        # CCXT Binance client
        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'
            }
        })
        
        # Markets yükle
        try:
            self.exchange.load_markets()
            logger.info("Binance markets yüklendi")
        except Exception as e:
            logger.error(f"Markets yüklenemedi: {e}")
    
    def get_balance(self, currency: str = 'USDT') -> float:
        try:
            balance = self.exchange.fetch_balance({"type": "future"})
            return balance.get('free', {}).get(currency, 0.0)
        except Exception as e:
            logger.error(f"Bakiye alınamadı: {e}")
            return 0.0
    
    def get_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            fsymbol = self._to_futures_symbol(symbol)
            ticker = self.exchange.fetch_ticker(fsymbol)
            return ticker
        except Exception as e:
            logger.error(f"Ticker alınamadı {symbol}: {e}")
            return None
    
    def get_funding_rate(self, symbol: str) -> tuple[float, int]:
        try:
            time.sleep(0.1)  
            
            url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&limit=1"
            import requests
            r = requests.get(url, timeout=10)
            
            if r.status_code != 200:
                logger.warning(f"{symbol}: Funding Rate API hatası - Status: {r.status_code}")
                return 0.0, int(time.time() * 1000)
                
            data = r.json()
            if isinstance(data, list) and data:
                return float(data[0]['fundingRate']), data[0]['fundingTime']
            elif isinstance(data, dict) and 'code' in data:
                logger.warning(f"{symbol}: Funding Rate API hatası - {data.get('msg', 'Bilinmeyen hata')}")
                return 0.0, int(time.time() * 1000)
            return 0.0, int(time.time() * 1000)
        except requests.exceptions.Timeout:
            logger.warning(f"{symbol}: Funding Rate API timeout")
            return 0.0, int(time.time() * 1000)
        except Exception as e:
            logger.error(f"Funding rate alınamadı {symbol}: {e}")
            return 0.0, int(time.time() * 1000)
    
    def get_open_interest(self, symbol: str) -> Optional[float]:
        try:
            time.sleep(0.1)  
            
            url = f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}"
            import requests
            r = requests.get(url, timeout=10)
            
            if r.status_code != 200:
                logger.warning(f"{symbol}: OpenInterest API hatası - Status: {r.status_code}")
                return None
                
            data = r.json()
            if isinstance(data, dict) and 'openInterest' in data:
                return float(data['openInterest'])
            elif isinstance(data, dict) and 'code' in data:
                # Binance API hatası
                logger.warning(f"{symbol}: OpenInterest API hatası - {data.get('msg', 'Bilinmeyen hata')}")
                return None
            else:
                logger.warning(f"{symbol}: OpenInterest verisi alınamadı - Response: {data}")
                return None
        except requests.exceptions.Timeout:
            logger.warning(f"{symbol}: OpenInterest API timeout")
            return None
        except Exception as e:
            logger.error(f"Open Interest alınamadı {symbol}: {e}")
            return None
    
    def get_volume_data(self, symbol: str, interval: str, limit: int) -> float:
        try:
            time.sleep(0.1)  
            
            url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
            import requests
            r = requests.get(url, timeout=10)
            
            if r.status_code != 200:
                logger.warning(f"{symbol}: Volume API hatası - Status: {r.status_code}")
                return 0.0
                
            data = r.json()
            if isinstance(data, list):
                return sum([float(k[5]) * float(k[4]) for k in data])
            elif isinstance(data, dict) and 'code' in data:
                logger.warning(f"{symbol}: Volume API hatası - {data.get('msg', 'Bilinmeyen hata')}")
                return 0.0
            return 0.0
        except requests.exceptions.Timeout:
            logger.warning(f"{symbol}: Volume API timeout")
            return 0.0
        except Exception as e:
            logger.error(f"Hacim verisi alınamadı {symbol}: {e}")
            return 0.0
    
    def get_klines(self, symbol: str, interval: str, limit: int) -> List[Dict[str, Any]]:
        try:
            fsymbol = self._to_futures_symbol(symbol)
            klines = self.exchange.fetch_ohlcv(fsymbol, interval, limit=limit)
            
            formatted_klines = []
            for k in klines:
                formatted_klines.append({
                    'timestamp': k[0],
                    'open': k[1],
                    'high': k[2],
                    'low': k[3],
                    'close': k[4],
                    'volume': k[5]
                })
            
            return formatted_klines
        except Exception as e:
            logger.error(f"Kline verisi alınamadı {symbol}: {e}")
            return []

    def get_order_book(self, symbol: str, limit: int = 10) -> Dict[str, Any]:
        try:
            fsymbol = self._to_futures_symbol(symbol)
            order_book = self.exchange.fetch_order_book(fsymbol, limit)
            return order_book or {}
        except Exception as e:
            logger.error(f"Order book alınamadı {symbol}: {e}")
            return {}

    def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            fsymbol = self._to_futures_symbol(symbol)
            trades = self.exchange.fetch_trades(fsymbol, limit=limit)
            return trades or []
        except Exception as e:
            logger.error(f"Recent trades alınamadı {symbol}: {e}")
            return []
    
    def get_market_data(self, symbol: str, lookback: int = 20) -> Dict[str, Any]:
        try:
            klines = self.get_klines(symbol, config.trading.interval, lookback)
            if not klines:
                return {}
            
            prices = [k['close'] for k in klines]
            volumes = [k['volume'] for k in klines]
            
            current_price = prices[-1]
            price_change = (current_price - prices[0]) / prices[0] if prices[0] > 0 else 0.0
            
            if len(prices) >= 20:
                returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
                volatility = sum(returns) / len(returns) if returns else 0.0
            else:
                volatility = 0.0
            
            short_ma = sum(prices[-5:]) / 5 if len(prices) >= 5 else current_price
            long_ma = sum(prices[-20:]) / 20 if len(prices) >= 20 else current_price
            
            rsi = self._calculate_rsi(prices)
            
            bb_position = self._calculate_bb_position(prices, current_price)
            
            return {
                'current_price': current_price,
                'price_history': prices,
                'volume_history': volumes,
                'price_change': price_change,
                'volatility': volatility,
                'short_ma': short_ma,
                'long_ma': long_ma,
                'rsi': rsi,
                'bb_position': bb_position,
                'volume': volumes[-1] if volumes else 0,
                'avg_volume': sum(volumes) / len(volumes) if volumes else 0
            }
            
        except Exception as e:
            logger.error(f"Market verisi alınamadı {symbol}: {e}")
            return {}
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gains = sum(gains[-period:]) / period
        avg_losses = sum(losses[-period:]) / period
        
        if avg_losses == 0:
            return 100.0
        
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_bb_position(self, prices: List[float], current_price: float, period: int = 20, std_dev: float = 2) -> float:
        if len(prices) < period:
            return 0.5
        
        sma = sum(prices[-period:]) / period
        variance = sum((p - sma) ** 2 for p in prices[-period:]) / period
        std = variance ** 0.5
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        if upper_band == lower_band:
            return 0.5
        
        # 0 = lower band, 1 = upper band
        position = (current_price - lower_band) / (upper_band - lower_band)
        return max(0, min(1, position))
    
    def _to_futures_symbol(self, symbol: str) -> str:
        if '/' in symbol:
            base, quote = symbol.split('/')
            return f"{base}/{quote}" if quote.upper() == 'USDT' else symbol
        if symbol.upper().endswith('USDT'):
            base = symbol[:-4]
            return f"{base}/USDT"
        return symbol
    
    def is_valid_futures_symbol(self, symbol: str) -> bool:
        try:
            fsymbol = self._to_futures_symbol(symbol)
            market = self.exchange.market(fsymbol)
            return market.get('active', False) and market.get('swap', False)
        except Exception:
            return False
    
    def prepare_market(self, symbol: str) -> tuple[str, Dict[str, Any]]:
        try:
            fsymbol = self._to_futures_symbol(symbol)
            market = self.exchange.market(fsymbol)
            
            try:
                self.exchange.set_margin_mode('ISOLATED', market['id'])
            except Exception:
                pass
            
            try:
                self.exchange.set_leverage(self.leverage, market['id'])
            except Exception:
                pass
            
            return fsymbol, market
        except Exception as e:
            logger.error(f"Market hazırlığı başarısız {symbol}: {e}")
            return symbol, {}
    
    def create_order(self, symbol: str, side: str, amount: float, order_type: str = 'market', **kwargs) -> Optional[Dict[str, Any]]:
        try:
            fsymbol, market = self.prepare_market(symbol)
            
            params = kwargs.get('params', {})
            
            if 'positionSide' in kwargs:
                position_side = kwargs.pop('positionSide')
                if position_side in ['LONG', 'SHORT']:
                    params['positionSide'] = position_side
                else:
                    logger.warning(f"Geçersiz positionSide değeri: {position_side}")
            
            special_params = ['timeInForce', 'closePosition', 'workingType', 'priceProtect']
            for param in special_params:
                if param in kwargs:
                    params[param] = kwargs.pop(param)
            
            if 'reduceOnly' in kwargs:
                kwargs.pop('reduceOnly')
                logger.info(f"{symbol}: reduceOnly parametresi kaldırıldı (Binance Futures uyumsuzluğu)")
            
            kwargs['params'] = params
            
            if order_type == 'market':
                if side.upper() == 'BUY':
                    order = self.exchange.create_market_buy_order(fsymbol, amount, **kwargs)
                else:
                    order = self.exchange.create_market_sell_order(fsymbol, amount, **kwargs)
            else:
                order = self.exchange.create_order(fsymbol, order_type, side, amount, **kwargs)
            
            logger.info(f"Emir oluşturuldu: {symbol} {side} {amount}")
            return order
            
        except Exception as e:
            logger.error(f"Emir oluşturulamadı {symbol}: {e}")
            return None
    
    def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            positions = self.exchange.fetch_positions()
            
            if not symbol:
                return positions
            
            fsymbol = self._to_futures_symbol(symbol)
            filtered_positions = []
            
            for pos in positions:
                unified_symbol = pos.get('symbol')
                raw_symbol = (pos.get('info') or {}).get('symbol')
                
                if (unified_symbol == fsymbol or 
                    unified_symbol == symbol or
                    raw_symbol == symbol or
                    raw_symbol == symbol.replace('/', '') or
                    raw_symbol == fsymbol.replace('/', '')):
                    filtered_positions.append(pos)
            
            return filtered_positions
            
        except Exception as e:
            logger.error(f"Pozisyonlar alınamadı: {e}")
            return []
    
    def is_position_open(self, symbol: str, position_type: str) -> bool:
        try:
            fsymbol = self._to_futures_symbol(symbol)
            positions = self.get_positions(fsymbol)
            
            for p in positions:
                unified_symbol = p.get('symbol')
                raw_symbol = (p.get('info') or {}).get('symbol')
                if unified_symbol != fsymbol and raw_symbol not in {symbol, symbol.replace('/', ''), fsymbol.replace('/', '')}:
                    continue
                
                contracts = float(p.get('contracts', 0))
                if contracts <= 0:
                    continue
                
                side = p.get('side', '').lower()
                
                if position_type == 'LONG':
                    if side == 'long' or (side == 'buy' and contracts > 0):
                        logger.debug(f"{symbol} LONG pozisyonu bulundu: {contracts}")
                        return True
                
                elif position_type == 'SHORT':
                    if side == 'short' or (side == 'sell' and contracts > 0):
                        logger.debug(f"{symbol} SHORT pozisyonu bulundu: {contracts}")
                        return True
            
            logger.debug(f"{symbol} {position_type} pozisyonu bulunamadı")
            return False
            
        except Exception as e:
            logger.error(f"Pozisyon kontrolü başarısız {symbol}: {e}")
            return True
