
import time
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

# Proje modülleri
from config import config
from strategies.strategy_manager import StrategyManager
from clients.binance_client import BinanceClient
from clients.telegram_client import TelegramClient
from trading.position_manager import PositionManager
from agents.market_analyst import MarketAnalyst
from utils.helpers import rate_limit_delay

# Logging ayarları
logging.basicConfig(
    level=logging.DEBUG,  # DEBUG seviyesine çıkar
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),  # UTF-8 encoding ekle
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class BalinaBot:
    
    def __init__(self):
        self.config = config
        self.strategy_manager = StrategyManager()
        self.binance_client = BinanceClient()
        self.telegram_client = TelegramClient()
        self.telegram_client = TelegramClient()
        self.position_manager = PositionManager()
        self.market_analyst = MarketAnalyst()
        
        self.position_manager.set_market_analyst(self.market_analyst)
        
        self.is_running = False
        self.symbols: List[str] = []
        self.previous_oi: Dict[str, float] = {}
        self.cooldown_until: Dict[str, float] = {}
        
        self.market_data_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info("BalinaBot başlatıldı")
    
    def load_symbols(self) -> bool:
        try:
            with open("binance_futures_symbols.json", "r") as f:
                data = json.load(f)
                raw_symbols = [s.replace("/", "").upper() for s in data.get("symbols", [])]
            
            valid_symbols = []
            for symbol in raw_symbols:
                if not symbol.endswith('USDT'):
                    continue
                    
                if self.binance_client.is_valid_futures_symbol(symbol):
                    valid_symbols.append(symbol)
                else:
                    logger.debug(f"Geçersiz futures sembolü: {symbol}")
            
            self.symbols = valid_symbols
            logger.info(f"{len(self.symbols)} geçerli futures sembolü yüklendi (toplam: {len(raw_symbols)})")
            return True
            
        except Exception as e:
            logger.error(f"Sembol listesi yüklenemedi: {e}")
            return False
    
    def get_market_data(self, symbol: str) -> Dict[str, Any]:
        try:
            funding_rate, funding_time = self.binance_client.get_funding_rate(symbol)
            current_oi = self.binance_client.get_open_interest(symbol)
            volume = self.binance_client.get_volume_data(symbol, self.config.trading.interval, self.config.trading.lookback)
            
            if current_oi is None:
                logger.debug(f"{symbol}: Open Interest verisi alınamadı, sembol atlanıyor")
                return {}
            
            previous_oi = self.previous_oi.get(symbol, current_oi)
            oi_change = (current_oi - previous_oi) / previous_oi if previous_oi > 0 else 0.0
            
            advanced_market_data = self.binance_client.get_market_data(symbol, 20)
            
            if not advanced_market_data:
                logger.debug(f"{symbol}: Gelişmiş market verisi alınamadı, temel verilerle devam ediliyor")
                advanced_market_data = {
                    'current_price': 0.0,
                    'price_change': 0.0,
                    'volatility': 0.0
                }
            
            btc_dominance = 0.5  
            market_cap_change = 0.0  
            volatility_index = advanced_market_data.get('volatility', 0.0)
            
            market_data = {
            market_data = {
                'funding_rate': funding_rate,
                'funding_time': funding_time,
                'oi_change': oi_change,
                'volume': volume,
                'price_change': advanced_market_data.get('price_change', 0.0),
                'rsi': advanced_market_data.get('rsi', 50.0),
                'volatility': volatility_index,
                'btc_dominance': btc_dominance,
                'market_cap_change': market_cap_change,
                'volatility_index': volatility_index,
                'market_data': {symbol: advanced_market_data}
            }
            
            self.market_data_cache[symbol] = market_data
            
            return market_data
            
        except Exception as e:
            logger.error(f"Market verisi alınamadı {symbol}: {e}")
            return {}
    
    def analyze_symbol(self, symbol: str) -> Dict[str, Any]:
        try:
            market_data = self.get_market_data(symbol)
            if not market_data:
                return {'signal': 'NEUTRAL', 'confidence': 0.0, 'reason': 'Veri alınamadı'}
            
            signal_result = self.strategy_manager.get_consolidated_signal(symbol, market_data)
            
            result = {
                'signal': signal_result.action,
                'confidence': signal_result.confidence,
                'reason': signal_result.reason,
                'strategy_results': signal_result.metadata.get('strategy_results', {}),
                'market_data': market_data
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Sembol analizi başarısız {symbol}: {e}")
            return {'signal': 'NEUTRAL', 'confidence': 0.0, 'reason': f'Hata: {e}'}
    
    def should_open_position(self, analysis: Dict[str, Any]) -> bool:
        signal = analysis.get('signal', 'NEUTRAL')
        confidence = analysis.get('confidence', 0.0)
        
        if signal not in ['LONG', 'SHORT']:
            return False
        
        if confidence < 0.7:
            logger.info(f"[WARNING] Sinyal güvenilirliği yetersiz: {confidence:.2f} < 0.7 (minimum: 0.7)")
            return False
        
        if self.position_manager.get_position_count() > 0:
            return False
        
        market_data = analysis.get('market_data', {})
        if not self._validate_market_data_quality(market_data):
            logger.info(f"[WARNING] Market veri kalitesi yetersiz: {signal}")
            return False
        
        logger.info(f"Güçlü sinyal tespit edildi: {signal} - Güven: {confidence:.2f}")
        return True
    
    def _validate_market_data_quality(self, market_data: Dict[str, Any]) -> bool:
        try:
            required_fields = ['funding_rate', 'oi_change', 'volume', 'price_change', 'volatility']
            for field in required_fields:
                if field not in market_data:
                    logger.info(f"[WARNING] Eksik veri alanı: {field}")
                    return False
            
            funding_rate = abs(market_data.get('funding_rate', 0))
            if funding_rate < 0.00001:      
                logger.info(f"[WARNING] Funding rate çok düşük: {funding_rate:.6f} < 0.00001 (%0.001)")
                return False
            
            volume = market_data.get('volume', 0)
            if volume < 100_000: 
                logger.info(f"[WARNING] Hacim çok düşük: {volume:,.0f} < 100,000 USD")
                return False
            
            volatility = abs(market_data.get('volatility', 0))
            if volatility < 0.0001:         
                logger.info(f"[WARNING] Volatilite çok düşük: {volatility:.6f} < 0.0001 (%0.01)")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Market veri kalitesi kontrolü hatası: {e}")
            return False
    
    def _check_daily_trade_limit(self) -> bool:
        return True
    
    def process_symbol(self, symbol: str) -> bool:
        try:
            if symbol in self.cooldown_until and time.time() < self.cooldown_until[symbol]:
                remaining = int(self.cooldown_until[symbol] - time.time())
                logger.debug(f"{symbol} cooldown aktif ({remaining}s). Atlanıyor.")
                return False
            
            analysis = self.analyze_symbol(symbol)
            technical_signal = analysis.get('signal', 'NEUTRAL')
            
            if technical_signal in ['LONG', 'SHORT']:
                logger.info(f"Teknik Sinyal: {technical_signal} ({symbol}). AI Analizi başlatılıyor...")
                market_data = analysis.get('market_data', {})
                
                ai_result = self.market_analyst.analyze_market_context(symbol, market_data, technical_signal)
                ai_action = ai_result.get('action', 'NEUTRAL')
                ai_confidence = ai_result.get('confidence', 0)
                ai_reasoning = ai_result.get('reasoning', '')
                
                logger.info(f"AI Görüşü: {ai_action} (Güven: {ai_confidence}) - {ai_reasoning}")
                
                if (technical_signal == 'LONG' and ai_action == 'SHORT') or \
                   (technical_signal == 'SHORT' and ai_action == 'LONG'):
                    logger.warning(f"AI VETO: Teknik ({technical_signal}) ve AI ({ai_action}) zıt düşüyor. İşlem iptal.")
                    return False
                    
                if ai_confidence < 30: 
                     logger.warning(f"AI VETO: AI güven skoru çok düşük ({ai_confidence}). İşlem iptal.")
                     return False

                if ai_action == 'NEUTRAL':
                    logger.warning(f"AI VETO: AI kararsız (NEUTRAL). İşlem iptal.")
                    return False

                
                analysis['ai_confirmation'] = True
                analysis['ai_reason'] = ai_reasoning
                analysis['ai_confidence'] = ai_confidence
                
            signal = analysis.get('signal', 'NEUTRAL')
            confidence = analysis.get('confidence', 0.0)
            
            if self.should_open_position(analysis):
                reason_msg = analysis['reason']
                if 'ai_reason' in analysis:
                     reason_msg += f"\n🤖 AI: {analysis['ai_reason']}"

                logger.info(f"[POSITION] POZİSYON AÇMA SİNYALİ ALINDI: {symbol} {signal} - Güven: {confidence:.2f}")
                
                self.telegram_client.send_alert(
                    symbol, 
                    signal, 
                    confidence, 
                    reason_msg, 
                    analysis['market_data']
                )
                
                success, order, message = self.position_manager.open_position(
                    symbol, 
                    analysis['signal'], 
                    analysis['confidence'], 
                    analysis['market_data']
                )
                
                if success:
                    logger.info(f"[SUCCESS] POZİSYON AÇILDI: {symbol} {analysis['signal']}")
                    
                    try:
                        balance = self.binance_client.get_balance("USDT")
                        self.telegram_client.send_position_opened(
                            symbol, 
                            analysis['signal'], 
                            order.get('amount', 0) if order else 0,
                            order.get('average', 0) if order else 0,
                            balance
                        )
                    except Exception as e:
                        logger.error(f"Pozisyon açıldı mesajı gönderilemedi: {e}")
                    
                    self.cooldown_until[symbol] = time.time() + (3 * 60)  
                    
                    return True
                else:
                    logger.warning(f"[ERROR] Pozisyon açılamadı {symbol}: {message}")
            else:
                signal = analysis.get('signal', 'NEUTRAL')
                confidence = analysis.get('confidence', 0.0)
                if signal in ['LONG', 'SHORT']:
                    logger.debug(f"[THRESHOLD] Sinyal tespit edildi ama eşik altında: {symbol} {signal} - Güven: {confidence:.2f} < 0.7")
            
            if 'market_data' in analysis and 'oi_change' in analysis['market_data']:
                current_oi = self.binance_client.get_open_interest(symbol)
                if current_oi is not None:
                    self.previous_oi[symbol] = current_oi
            
            return False
            
        except Exception as e:
            logger.error(f"Sembol işleme hatası {symbol}: {e}")
            return False

    def validate_config(self) -> bool:
        """Gerekli konfigürasyonun tam olduğunu kontrol et"""
        if not self.config.binance_api_key or not self.config.binance_api_secret:
            logger.critical("API anahtarları eksik! Bot başlatılamıyor.")
            logger.critical("Lütfen .env dosyasını oluşturun ve BINANCE_API_KEY ile BINANCE_API_SECRET değerlerini girin.")
            return False
        return True

    def run_monitor(self):
        try:
            if not self.validate_config():
                return

            if not self.load_symbols():
                logger.error("Sembol listesi yüklenemedi. Bot durduruluyor.")
                return
            
            if not self.telegram_client.test_connection():
                logger.warning("Telegram bağlantısı başarısız! Bot çalışmaya devam edecek ama bildirim gelmeyebilir.")
            else:
                self.telegram_client.send_test_message()
            
            balance = self.binance_client.get_balance("USDT")
            start_msg = (
                f"🤖 *Agent Başladı (Güvenli Mod)*\n"
                f"💰 Kullanılabilir Bakiye: `${balance:.2f}` USDT\n"
                f"📊 Takip Edilen Coin Sayısı: {len(self.symbols)}\n"
                f"⚡ Kaldıraç: {self.config.trading.leverage}x"
            )
            self.telegram_client.send_message(start_msg)
            
            logger.info(f"Agent aktif - {len(self.symbols)} sembol izleniyor")
            
            logger.info("Başlangıç verileri toplanıyor...")
            for symbol in self.symbols:
                oi = self.binance_client.get_open_interest(symbol)
                if oi is not None:
                    self.previous_oi[symbol] = oi
                rate_limit_delay(self.config.trading.api_delay)
            
            self.is_running = True
            error_count = 0
            
            while self.is_running:
                try:
                    self.position_manager.track_positions()
                    
                    if self.position_manager.get_position_count() == 0:
                        for symbol in self.symbols:
                            if self.process_symbol(symbol):
                                break   
                            
                            rate_limit_delay(self.config.trading.api_delay)
                    
                    error_count = 0
                    
                    time.sleep(30)
                    
                except KeyboardInterrupt:
                    logger.info("Bot kullanıcı tarafından durduruldu")
                    break
                except Exception as e:
                    error_count += 1
                    wait_time = min(30 * error_count, 300)  # Artan bekleme süresi (max 5 dk)
                    logger.error(f"Ana döngü hatası ({error_count}. kez): {e}")
                    logger.info(f"{wait_time} saniye bekleniyor...")
                    time.sleep(wait_time)
            
        except Exception as e:
            logger.critical(f"Bot başlatma hatası: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Botu durdur"""
        self.is_running = False
        
        if self.position_manager.get_position_count() > 0:
            logger.info("Bot durduruluyor, tüm pozisyonlar kapatılıyor...")
            results = self.position_manager.close_all_positions("Bot durduruldu")
            
            for symbol, message in results.items():
                logger.info(f"{symbol}: {message}")
        
        try:
            trading_summary = self.position_manager.get_trading_summary()
            if trading_summary:
                logger.info("Detaylı trading raporu Telegram'a gönderiliyor...")
                self.telegram_client.send_trading_report(trading_summary)
            else:
                logger.warning("Trading raporu alınamadı")
        except Exception as e:
            logger.error(f"Trading raporu gönderilemedi: {e}")
        
        self.telegram_client.send_bot_status("stopped", {
            "Total PnL": f"${self.position_manager.get_total_pnl():.2f}",
            "Active Positions": self.position_manager.get_position_count()
        })
        
        logger.info("Bot durduruldu")

def main():
    try:
        bot = BalinaBot()
        bot.run_monitor()
    except KeyboardInterrupt:
        logger.info("Program kullanıcı tarafından durduruldu")
    except Exception as e:
        logger.error(f"Program hatası: {e}")

if __name__ == "__main__":
    main()
