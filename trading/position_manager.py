import time
import logging
from typing import Dict, Any, Optional, Tuple, List
from config import config
from clients.binance_client import BinanceClient
from clients.telegram_client import TelegramClient

logger = logging.getLogger(__name__)

class PositionManager:
    Pozisyon yönetimi sınıfı

    def __init__(self):
        self.binance_client = BinanceClient()
        self.telegram_client = TelegramClient()
        self.active_positions: Dict[str, Dict[str, Any]] = {}
        self.market_analyst = None

        self.trade_history: List[Dict[str, Any]] = []
        self.total_trades = 0
        self.profitable_trades = 0
        self.losing_trades = 0
        self.total_profit = 0.0
        self.total_loss = 0.0

    def set_market_analyst(self, analyst) -> None:
        Market Analyst'i bağla
        self.market_analyst = analyst

    def open_position(self, symbol: str, action: str, confidence: float,
                     market_data: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        Pozisyon aç
        try:
            balance = self.binance_client.get_balance("USDT")
            if balance <= 0:
                return False, None, "Yetersiz bakiye"

            if self.get_position_count() > 0:
                return False, None, "Zaten aktif pozisyon var"

            fsymbol, market = self.binance_client.prepare_market(symbol)
            if not market:
                return False, None, "Market hazırlığı başarısız"

            amount = self._calculate_position_size(symbol, balance, confidence, market_data)
            if amount <= 0:
                return False, None, "Pozisyon miktarı hesaplanamadı"

            order_params = {"positionSide": action}
            logger.info(f"Emir oluşturuluyor: {symbol} {action} {amount} - Parametreler: {order_params}")

            if action == "LONG":
                order = self.binance_client.create_order(symbol, "BUY", amount, "market", **order_params)
            else:
                order = self.binance_client.create_order(symbol, "SELL", amount, "market", **order_params)

            if not order:
                return False, None, "Emir oluşturulamadı"

            time.sleep(2)
            is_position_open = self.binance_client.is_position_open(symbol, action)

            if not is_position_open:
                logger.warning(f"{symbol} {action} pozisyonu emir başarılı ama pozisyon açılmadı")
                return False, None, "Emir başarılı ama pozisyon açılmadı"

            entry_price = order.get('average', market_data.get('current_price', 0))
            position_info = {
                'symbol': symbol,
                'action': action,
                'amount': amount,
                'entry_price': entry_price,
                'entry_time': time.time(),
                'confidence': confidence,
                'order_id': order.get('id'),
                'market_data': market_data
            }

            self.active_positions[symbol] = position_info

            self.telegram_client.send_position_opened(
                symbol, action, amount, entry_price, balance
            )

            logger.info(f"Pozisyon açıldı: {symbol} {action} {amount} @ {entry_price}")
            return True, order, "Pozisyon başarıyla açıldı"

        except Exception as e:
            error_msg = f"Pozisyon açma hatası: {e}"
            logger.error(error_msg)
            return False, None, error_msg

    def close_position(self, symbol: str, reason: str = "Manual") -> Tuple[bool, str]:
        Pozisyon kapat
        try:
            if symbol not in self.active_positions:
                return False, "Aktif pozisyon bulunamadı"

            position = self.active_positions[symbol]
            action = position['action']
            amount = position['amount']
            entry_price = position['entry_price']

            ticker = self.binance_client.get_ticker(symbol)
            if not ticker:
                return False, "Güncel fiyat alınamadı"

            current_price = ticker['last']

            order_params = {"positionSide": action}
            logger.info(f"Pozisyon kapatılıyor: {symbol} {action} {amount} - Parametreler: {order_params}")

            if action == "LONG":
                order = self.binance_client.create_order(symbol, "SELL", amount, "market", **order_params)
            else:
                order = self.binance_client.create_order(symbol, "BUY", amount, "market", **order_params)

            if not order:
                return False, "Pozisyon kapatma emri oluşturulamadı"

            time.sleep(2)
            is_position_open = self.binance_client.is_position_open(symbol, action)

            if is_position_open:
                logger.warning(f"{symbol} {action} pozisyonu emir başarılı ama pozisyon hala açık")
                return False, "Emir başarılı ama pozisyon hala açık"

            if action == "LONG":
                pnl = (current_price - entry_price) * amount
                raw_pnl_pct = (current_price - entry_price) / entry_price * 100
            else:
                pnl = (entry_price - current_price) * amount
                raw_pnl_pct = (entry_price - current_price) / entry_price * 100

            leveraged_pnl_pct = raw_pnl_pct * config.trading.leverage

            trade_record = {
                'symbol': symbol,
                'action': action,
                'amount': amount,
                'entry_price': entry_price,
                'exit_price': current_price,
                'pnl': pnl,
                'leveraged_pnl_pct': leveraged_pnl_pct,
                'entry_time': position['entry_time'],
                'exit_time': time.time(),
                'reason': reason
            }
            self.trade_history.append(trade_record)

            self.total_trades += 1
            if pnl > 0:
                self.profitable_trades += 1
                self.total_profit += pnl
            else:
                self.losing_trades += 1
                self.total_loss += abs(pnl)

            self.telegram_client.send_position_closed(
                symbol, action, amount, entry_price, current_price, pnl, leveraged_pnl_pct
            )

            del self.active_positions[symbol]

            logger.info(f"Pozisyon kapatıldı: {symbol} {action} - PnL: {pnl:.2f} USD ({leveraged_pnl_pct:.2f}%)")
            return True, f"Pozisyon kapatıldı - PnL: {pnl:.2f} USD"

        except Exception as e:
            error_msg = f"Pozisyon kapatma hatası: {e}"
            logger.error(error_msg)
            return False, error_msg

    def track_positions(self) -> None:
        Aktif pozisyonları takip et
        try:
            for symbol, position in list(self.active_positions.items()):
                is_open = self.binance_client.is_position_open(symbol, position['action'])
                if not is_open:
                    time.sleep(2)
                    if not self.binance_client.is_position_open(symbol, position['action']):
                        logger.info(f"{symbol} {position['action']} pozisyonu Binance'de bulunamadı - manuel kapatıldı olabilir (çift doğrulama)")
                        self.telegram_client.send_message(f"[INFO] {symbol} {position['action']} pozisyonu Binance'de bulunamadı - manuel kapatıldı olabilir.")
                        del self.active_positions[symbol]
                        continue

                ticker = self.binance_client.get_ticker(symbol)
                if not ticker:
                    continue

                current_price = ticker['last']
                entry_price = position['entry_price']
                action = position['action']

                try:
                    positions = self.binance_client.exchange.fetch_positions()
                    position_data = None

                    fsymbol = self.binance_client._to_futures_symbol(symbol)

                    for pos in positions:
                        pos_symbol = pos['symbol']
                        pos_side = pos['side'].lower()

                        symbol_match = (
                            pos_symbol == fsymbol or
                            pos_symbol == symbol or
                            pos_symbol == f"{symbol}:USDT" or
                            pos_symbol == f"{fsymbol}:USDT" or
                            pos_symbol.replace(':USDT', '') == symbol or
                            pos_symbol.replace(':USDT', '') == fsymbol
                        )

                        if symbol_match and pos_side == action.lower() and pos['contracts'] > 0:
                            position_data = pos
                            break

                    if position_data and position_data['contracts'] > 0:
                        unrealized_pnl_pct = float(position_data.get('percentage') or 0.0)

                        if unrealized_pnl_pct >= config.trading.take_profit_percent:
                            logger.info(f"[PROFIT] {symbol} {action} pozisyonu %{unrealized_pnl_pct:.2f} kar ile otomatik kapatılıyor!")
                            self.close_position(symbol, f"Kar al hedefine ulaşıldı: %{unrealized_pnl_pct:.2f}")

                        elif unrealized_pnl_pct <= -config.trading.stop_loss_percent:
                            logger.info(f"[STOP_LOSS] {symbol} {action} pozisyonu %{unrealized_pnl_pct:.2f} zarar ile otomatik kapatılıyor!")
                            self.close_position(symbol, f"Zarar kes hedefine ulaşıldı: %{unrealized_pnl_pct:.2f}")
                    else:
                        logger.warning(f"{symbol} {action} pozisyonu Binance'de bulunamadı (fsymbol: {fsymbol})")

                except Exception as e:
                    logger.error(f"PnL hesaplama hatası {symbol}: {e}")
                    if action == "LONG":
                        raw_pnl_pct = (current_price - entry_price) / entry_price * 100
                    else:
                        raw_pnl_pct = (entry_price - current_price) / entry_price * 100

                    if raw_pnl_pct >= (config.trading.take_profit_percent / config.trading.leverage):
                        logger.info(f"[PROFIT] {symbol} {action} pozisyonu %{raw_pnl_pct:.2f} kar ile otomatik kapatılıyor!")
                        self.close_position(symbol, f"Kar al hedefine ulaşıldı: %{raw_pnl_pct:.2f}")

                    elif raw_pnl_pct <= -(config.trading.stop_loss_percent / config.trading.leverage):
                        logger.info(f"[STOP_LOSS] {symbol} {action} pozisyonu %{raw_pnl_pct:.2f} zarar ile otomatik kapatılıyor!")
                        self.close_position(symbol, f"Zarar kes hedefine ulaşıldı: %{raw_pnl_pct:.2f}")

                position_age = time.time() - position['entry_time']
                max_duration = config.trading.position_duration_max * 60

                if position_age > max_duration:
                    logger.info(f"{symbol} {action} pozisyonu maksimum süre aşıldığı için kapatılıyor!")
                    self.close_position(symbol, f"Maksimum süre aşıldı: {position_age/60:.1f} dakika")

                last_check = position.get('last_ai_check', 0)
                if self.market_analyst and self.market_analyst.enabled and (time.time() - last_check > 120):
                    try:
                        market_data = position.get('market_data', {})
                        market_data['current_price'] = current_price

                        position['unrealized_pnl_pct'] = unrealized_pnl_pct if 'unrealized_pnl_pct' in locals() else 0.0

                        logger.info(f"[AI CHECK] AI Pozisyon Kontrolü: {symbol}...")
                        ai_decision = self.market_analyst.analyze_open_position(symbol, position, market_data)

                        ai_action = ai_decision.get('action')
                        ai_reason = ai_decision.get('reason')

                        if ai_action == 'CLOSE':
                            if -10.0 < unrealized_pnl_pct < 10.0 and ai_decision.get('confidence', 0) < 90:
                                log_msg = f"AI VETO EDİLDİ: AI kapatmak istedi ama PnL (%{unrealized_pnl_pct:.2f}) hedef aralığında değil (-10.0 ile 10.0 arası). Pozisyon korunuyor."
                                logger.info(log_msg)
                                self.telegram_client.send_message(f"🛡️ *AI KARARI VETO EDİLDİ* ({symbol})\nAI çıkmak istedi ama kar/zarar (%{unrealized_pnl_pct:.2f}) henüz +/- %10 limitine ulaşmadı. Pozisyon tutuluyor.")
                            else:
                                log_msg = f"AI KARARI: POZİSYONU KAPAT ({symbol}) - Sebep: {ai_reason} - Guven: %{ai_decision.get('confidence', 0)}"
                                logger.info(f"[AI CLOSE] {log_msg}")

                                tg_msg = f"🚨 *AI KARARI: POZİSYONU KAPAT* ({symbol})\n"
                                tg_msg += f"💡 Sebep: {ai_reason}\n"
                                tg_msg += f"📊 Güven: %{ai_decision.get('confidence', 0)}"
                                self.telegram_client.send_message(tg_msg)

                                self.close_position(symbol, f"AI Kararı: {ai_reason}")

                        elif ai_action == 'HOLD':
                            log_msg = f"AI KARARI: POZİSYONU TUT ({symbol}) - Sebep: {ai_reason} - Guven: %{ai_decision.get('confidence', 0)}"
                            logger.info(f"[AI HOLD] {log_msg}")

                            tg_msg = f"✅ *AI KARARI: POZİSYONU TUT* ({symbol})\n"
                            tg_msg += f"💡 Sebep: {ai_reason}\n"
                            tg_msg += f"📊 Güven: %{ai_decision.get('confidence', 0)}"
                            self.telegram_client.send_message(tg_msg)

                        position['last_ai_check'] = time.time()

                    except Exception as e:
                        logger.error(f"AI pozisyon kontrol hatası {symbol}: {e}")

        except Exception as e:
            logger.error(f"Pozisyon takibi hatası: {e}")

    def _calculate_position_size(self, symbol: str, balance: float, confidence: float,
                                market_data: Dict[str, Any]) -> float:
        Pozisyon miktarı hesaplama - Eski haline döndürüldü
        try:
            risk_multiplier = 0.5 + (confidence * 0.5)

            available_balance = balance * 0.95

            risk_amount = available_balance * risk_multiplier

            leveraged_amount = risk_amount * config.trading.leverage

            current_price = market_data.get('current_price', 0)
            if current_price <= 0:
                ticker = self.binance_client.get_ticker(symbol)
                if ticker:
                    current_price = ticker['last']
                else:
                    return 0.0

            token_amount = leveraged_amount / current_price

            fsymbol, market = self.binance_client.prepare_market(symbol)
            if not market:
                return 0.0

            limits = market.get('limits', {})
            min_amount = limits.get('amount', {}).get('min', 0)

            if min_amount > 0 and token_amount < min_amount:
                token_amount = min_amount

            min_cost = limits.get('cost', {}).get('min', 0)
            if min_cost > 0:
                notional = token_amount * current_price
                if notional < min_cost:
                    token_amount = min_cost / current_price

            logger.info(f"Pozisyon hesaplama: Bakiye=${balance:.2f}, Risk=${risk_amount:.2f}, Token={token_amount:.6f}, Notional=${token_amount * current_price:.2f}")

            return token_amount

        except Exception as e:
            logger.error(f"Pozisyon miktarı hesaplama hatası: {e}")
            return 0.0

    def get_active_positions(self) -> Dict[str, Dict[str, Any]]:
        Aktif pozisyonları getir
        return self.active_positions.copy()

    def get_position_count(self) -> int:
        Aktif pozisyon sayısını getir
        return len(self.active_positions)

    def get_total_pnl(self) -> float:
        Toplam PnL hesapla
        total_pnl = 0.0

        for symbol, position in self.active_positions.items():
            ticker = self.binance_client.get_ticker(symbol)
            if not ticker:
                continue

            current_price = ticker['last']
            entry_price = position['entry_price']
            amount = position['amount']
            action = position['action']

            if action == "LONG":
                pnl = (current_price - entry_price) * amount
            else:
                pnl = (entry_price - current_price) * amount

            total_pnl += pnl

        return total_pnl

    def close_all_positions(self, reason: str = "Manual") -> Dict[str, str]:
        Tüm pozisyonları kapat
        results = {}

        for symbol in list(self.active_positions.keys()):
            success, message = self.close_position(symbol, reason)
            results[symbol] = message

        return results

    def get_trading_summary(self) -> Dict[str, Any]:
        Trading özeti getir
        try:
            current_balance = self.binance_client.get_balance("USDT")

            net_pnl = self.total_profit - self.total_loss

            win_rate = (self.profitable_trades / self.total_trades * 100) if self.total_trades > 0 else 0

            avg_profit = self.total_profit / self.profitable_trades if self.profitable_trades > 0 else 0
            avg_loss = self.total_loss / self.losing_trades if self.losing_trades > 0 else 0

            recent_trades = self.trade_history[-10:] if len(self.trade_history) >= 10 else self.trade_history

            return {
                'total_trades': self.total_trades,
                'profitable_trades': self.profitable_trades,
                'losing_trades': self.losing_trades,
                'win_rate': win_rate,
                'total_profit': self.total_profit,
                'total_loss': self.total_loss,
                'net_pnl': net_pnl,
                'avg_profit': avg_profit,
                'avg_loss': avg_loss,
                'current_balance': current_balance,
                'recent_trades': recent_trades
            }

        except Exception as e:
            logger.error(f"Trading özeti alınamadı: {e}")
            return {}
