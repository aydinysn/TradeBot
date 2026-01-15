import requests
import logging
import time
from typing import Optional, Dict, Any
from config import config

logger = logging.getLogger(__name__)

class TelegramClient:
    
    
    def __init__(self):
        self.bot_token = config.telegram_bot_token
        self.chat_id = config.telegram_chat_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.last_message_time = 0
        self.min_message_interval = 3.0     
    
    def send_message(self, message: str, parse_mode: str = None) -> bool:
        try:
            current_time = time.time()
            time_since_last = current_time - self.last_message_time
            if time_since_last < self.min_message_interval:
                sleep_time = self.min_message_interval - time_since_last
                logger.debug(f"Rate limiting: {sleep_time:.2f} saniye bekleniyor")
                time.sleep(sleep_time)
            
            if len(message) > 4000:
                message = message[:4000] + "\n\n... (mesaj kısaltıldı)"
            
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "disable_web_page_preview": True 
            }
            
            if parse_mode:
                payload["parse_mode"] = parse_mode
            
            response = requests.post(url, data=payload, timeout=15)
            
            if response.status_code == 200:
                self.last_message_time = time.time()
                logger.info("Telegram mesajı başarıyla gönderildi")
                return True
            else:
                logger.error(f"Telegram mesajı gönderilemedi: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Telegram mesaj hatası: {e}")
            return False
    
    def _escape_markdown(self, text: str) -> str:
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    def _send_with_html(self, message: str) -> bool:
        try:
            html_message = self._markdown_to_html(message)
            
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": html_message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            
            response = requests.post(url, data=payload, timeout=15)
            
            if response.status_code == 200:
                logger.info("Telegram mesajı HTML formatında başarıyla gönderildi")
                return True
            else:
                logger.error(f"HTML mesajı da gönderilemedi: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"HTML mesaj hatası: {e}")
            return False
    
    def _markdown_to_html(self, text: str) -> str:
        text = text.replace('*', '<b>').replace('*', '</b>')
        text = text.replace('`', '<code>').replace('`', '</code>')
        text = text.replace('_', '<i>').replace('_', '</i>')
        return text
    
    def send_alert(self, symbol: str, action: str, confidence: float, reason: str, 
                   market_data: Optional[Dict[str, Any]] = None) -> bool:
        try:
            action_emoji = "🚀" if action == "LONG" else "📉" if action == "SHORT" else "⚠️"
            confidence_emoji = "🔥" if confidence > 0.8 else "⚡" if confidence > 0.6 else "💡"
            
            message = (
                f"{action_emoji} *TRADING ALERT: {symbol}*\n\n"
                f"🎯 Aksiyon: `{action}`\n"
                f"{confidence_emoji} Güvenilirlik: `%{confidence*100:.1f}`\n"
                f"📝 Sebep: {reason}\n"
            )
            
            if market_data:
                if 'current_price' in market_data:
                    message += f"💰 Fiyat: `{market_data['current_price']:.4f}`\n"
                if 'volume' in market_data:
                    message += f"📊 Hacim: `${market_data['volume']:,.0f}`\n"
                if 'price_change' in market_data:
                    change_pct = market_data['price_change'] * 100
                    change_emoji = "📈" if change_pct > 0 else "📉"
                    message += f"{change_emoji} Değişim: `%{change_pct:.2f}`\n"
            
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            message += f"\n🕒 {now}"
            
            return self.send_message(message)
            
        except Exception as e:
            logger.error(f"Alert mesajı oluşturulamadı: {e}")
            return False
    
    def send_position_opened(self, symbol: str, action: str, amount: float, 
                            price: float, usdt_balance: float) -> bool:
        try:
            action_emoji = "🚀" if action == "LONG" else "📉"
            action_text = "LONG" if action == "LONG" else "SHORT"
            
            message = (
                f"{action_emoji} *{action_text} Pozisyon Açıldı!*\n\n"
                f"📊 Sembol: `{symbol}`\n"
                f"💰 Fiyat: `{price:.4f}`\n"
                f"📈 Miktar: `{amount:.4f}`\n"
                f"💵 Kullanılan Bakiye: `${usdt_balance:.2f}`\n"
                f"⚡ Kaldıraç: `{config.trading.leverage}x`\n\n"
                f"🎯 Kar Al: `%{config.trading.take_profit_percent:.1f}`\n"
                f"🛑 Zarar Kes: `%{config.trading.stop_loss_percent:.1f}`"
            )
            
            return self.send_message(message)
            
        except Exception as e:
            logger.error(f"Pozisyon açıldı mesajı oluşturulamadı: {e}")
            return False
    
    def send_position_closed(self, symbol: str, action: str, amount: float, 
                            entry_price: float, exit_price: float, pnl: float, 
                            leveraged_pnl: float) -> bool:
        try:
            action_emoji = "🚀" if action == "LONG" else "📉"
            action_text = "LONG" if action == "LONG" else "SHORT"
            
            if pnl > 0:
                pnl_emoji = "✅"
                result_text = "KAR"
            elif pnl < 0:
                pnl_emoji = "❌"
                result_text = "ZARAR"
            else:
                pnl_emoji = "➖"
                result_text = "BAŞABAŞ"
            
            message = (
                f"{pnl_emoji} *Pozisyon Kapatıldı!*\n\n"
                f"📊 Sembol: `{symbol}`\n"
                f"📈 Tip: `{action_text}`\n"
                f"💰 Açılış Fiyatı: `{entry_price:.4f}`\n"
                f"💰 Kapanış Fiyatı: `{exit_price:.4f}`\n"
                f"📊 Miktar: `{amount:.4f}`\n"
                f"⚡ Kaldıraç: `{config.trading.leverage}x`\n\n"
                f"{pnl_emoji} Kar/Zarar: `${pnl:.2f}`\n"
                f"🚀 Kaldıraçlı PnL: `%{leveraged_pnl:.2f}`\n\n"
                f"🎯 Sonuç: **{result_text}**"
            )
            
            return self.send_message(message)
            
        except Exception as e:
            logger.error(f"Pozisyon kapandı mesajı oluşturulamadı: {e}")
            return False
    
    def send_bot_status(self, status: str, details: Optional[Dict[str, Any]] = None) -> bool:
        try:
            status_emoji = {
                'started': '🤖',
                'stopped': '⏹️',
                'error': '⚠️',
                'warning': '⚠️',
                'info': 'ℹ️'
            }.get(status, '📊')
            
            message = f"{status_emoji} *Bot Durumu: {status.upper()}*\n\n"
            
            if details:
                for key, value in details.items():
                    if isinstance(value, float):
                        message += f"📊 {key}: `{value:.2f}`\n"
                    else:
                        message += f"📊 {key}: `{value}`\n"
            
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            message += f"\n🕒 {now}"
            
            return self.send_message(message)
            
        except Exception as e:
            logger.error(f"Bot durum mesajı oluşturulamadı: {e}")
            return False
    
    def send_strategy_summary(self, strategy_results: Dict[str, Any]) -> bool:
        try:
            message = "📊 *Strateji Özeti*\n\n"
            
            for strategy_name, result in strategy_results.items():
                action_emoji = "🚀" if result['action'] == "LONG" else "📉" if result['action'] == "SHORT" else "➖"
                confidence = result['confidence'] * 100
                
                message += (
                    f"{action_emoji} **{strategy_name}**\n"
                    f"   Aksiyon: `{result['action']}`\n"
                    f"   Güvenilirlik: `%{confidence:.1f}`\n"
                    f"   Sebep: {result['reason']}\n\n"
                )
            
            return self.send_message(message)
            
        except Exception as e:
            logger.error(f"Strateji özeti mesajı oluşturulamadı: {e}")
            return False
    
    def send_trading_report(self, trading_summary: Dict[str, Any]) -> bool:
        try:
            total_trades = trading_summary.get('total_trades', 0)
            profitable_trades = trading_summary.get('profitable_trades', 0)
            losing_trades = trading_summary.get('losing_trades', 0)
            win_rate = trading_summary.get('win_rate', 0)
            net_pnl = trading_summary.get('net_pnl', 0)
            current_balance = trading_summary.get('current_balance', 0)
            
            if net_pnl > 0:
                overall_emoji = "✅"
                result_text = "TOPLAM KAR"
            elif net_pnl < 0:
                overall_emoji = "❌"
                result_text = "TOPLAM ZARAR"
            else:
                overall_emoji = "➖"
                result_text = "BAŞABAŞ"
            
            message = (
                f"📊 *TRADING RAPORU*\n\n"
                f"🎯 **Genel Özet**\n"
                f"   Toplam İşlem: `{total_trades}`\n"
                f"   Karlı İşlem: `{profitable_trades}`\n"
                f"   Zararlı İşlem: `{losing_trades}`\n"
                f"   Başarı Oranı: `%{win_rate:.1f}`\n\n"
                
                f"💰 **Finansal Durum**\n"
                f"   Toplam Kar: `${trading_summary.get('total_profit', 0):.2f}`\n"
                f"   Toplam Zarar: `${trading_summary.get('total_loss', 0):.2f}`\n"
                f"   Net Kar/Zarar: `${net_pnl:.2f}`\n"
                f"   Güncel Bakiye: `${current_balance:.2f}` USDT\n\n"
                
                f"📈 **Ortalama Değerler**\n"
                f"   Ortalama Kar: `${trading_summary.get('avg_profit', 0):.2f}`\n"
                f"   Ortalama Zarar: `${trading_summary.get('avg_loss', 0):.2f}`\n\n"
                
                f"{overall_emoji} **Sonuç: {result_text}**"
            )
            
            recent_trades = trading_summary.get('recent_trades', [])
            if recent_trades:
                message += "\n\n📋 **Son İşlemler**\n"
                for i, trade in enumerate(recent_trades[-5:], 1):  # Son 5 işlem
                    trade_emoji = "✅" if trade.get('pnl', 0) > 0 else "❌"
                    symbol = trade.get('symbol', 'N/A')
                    pnl = trade.get('pnl', 0)
                    action = trade.get('action', 'N/A')
                    
                    message += f"{i}. {trade_emoji} `{symbol}` {action} `${pnl:.2f}`\n"
            
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            message += f"\n\n🕒 {now}"
            
            return self.send_message(message)
            
        except Exception as e:
            logger.error(f"Trading raporu oluşturulamadı: {e}")
            return False
    
    def test_connection(self) -> bool:
        try:
            url = f"{self.base_url}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                bot_info = response.json()
                logger.info(f"Telegram bot bağlantısı başarılı: {bot_info['result']['username']}")
                return True
            else:
                logger.error(f"Telegram bot bağlantısı başarısız: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Telegram bağlantı testi başarısız: {e}")
            return False
    
    def send_test_message(self) -> bool:
        try:
            from datetime import datetime, timezone
            test_message = (
                "Bot Test Mesajı\n"
                "Telegram bağlantısı başarılı!\n"
                "Mesajlar düzgün geliyor.\n"
                "Test zamanı: " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            )
            
            return self.send_message(test_message, parse_mode=None) 
            
        except Exception as e:
            logger.error(f"Test mesajı gönderilemedi: {e}")
            return False
