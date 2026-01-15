from typing import Dict, Any, List, Tuple
from .base_strategy import BaseStrategy, SignalResult
from clients.binance_client import BinanceClient
import math


class NetOrderFlowStrategy(BaseStrategy):
    def __init__(self,
                 obi_threshold: float = 0.3,
                 cvd_window: int = 3,
                 vwap_tolerance_pct: float = 0.0005,
                 atr_multiplier_sl: float = 1.2,
                 max_spread_bps: float = 0.5,
                 max_slippage_pct: float = 0.001,
                 time_exit_minutes: int = 4):
        super().__init__(name="NetOrderFlow")
        self.client = BinanceClient()
        self.obi_threshold = obi_threshold
        self.cvd_window = cvd_window
        self.vwap_tolerance_pct = vwap_tolerance_pct
        self.atr_multiplier_sl = atr_multiplier_sl
        self.max_spread_bps = max_spread_bps
        self.max_slippage_pct = max_slippage_pct
        self.time_exit_minutes = time_exit_minutes

    def update_params(self, **kwargs) -> None:
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)

    def get_required_data(self) -> list:
        return ['market_data']

    def _calc_vwap(self, klines_1m: List[Dict[str, Any]]) -> float:
        num = 0.0
        den = 0.0
        for k in klines_1m:
            typical = (k['high'] + k['low'] + k['close']) / 3
            vol = k['volume']
            num += typical * vol
            den += vol
        return num / den if den > 0 else 0.0

    def _calc_atr1m(self, klines_1m: List[Dict[str, Any]]) -> float:
        if len(klines_1m) < 2:
            return 0.0
        trs: List[float] = []
        prev_close = klines_1m[0]['close']
        for k in klines_1m[1:]:
            high = k['high']
            low = k['low']
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
            prev_close = k['close']
        return sum(trs) / len(trs) if trs else 0.0

    def _calc_cvd(self, trades: List[Dict[str, Any]]) -> float:
            cvd = 0.0
        for t in trades[-self.cvd_window:]:
            side = (t.get('side') or '').lower()
            amount = float(t.get('amount', 0))
            if side == 'buy':
                cvd += amount
            elif side == 'sell':
                cvd -= amount
        return cvd

    def _calc_obi(self, order_book: Dict[str, Any], levels: int = 10) -> float:
        bids = order_book.get('bids') or []
        asks = order_book.get('asks') or []
        bid_vol = sum([b[1] for b in bids[:levels]]) if bids else 0.0
        ask_vol = sum([a[1] for a in asks[:levels]]) if asks else 0.0
        denom = bid_vol + ask_vol
        if denom == 0:
            return 0.0
        return (bid_vol - ask_vol) / denom

    def _calc_spread_bps(self, order_book: Dict[str, Any]) -> Tuple[float, float, float]:
        bids = order_book.get('bids') or []
        asks = order_book.get('asks') or []
        if not bids or not asks:
            return 0.0, 0.0, 0.0
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        mid = (best_bid + best_ask) / 2
        spread_bps = ((best_ask - best_bid) / mid) * 10000 if mid > 0 else 0.0
        return spread_bps, best_bid, best_ask

    def _estimate_slippage_pct(self, amount: float, side: str, order_book: Dict[str, Any]) -> float:
        if amount <= 0:
            return 0.0
        book_side = (order_book.get('asks') if side == 'BUY' else order_book.get('bids')) or []
        remaining = amount
        notional_cost = 0.0
        filled = 0.0
        for price, size in book_side:
            take = min(size, remaining)
            notional_cost += price * take
            filled += take
            remaining -= take
            if remaining <= 0:
                break
        if filled <= 0:
            return 1.0
        avg_fill = notional_cost / filled
        bids = order_book.get('bids') or []
        asks = order_book.get('asks') or []
        if not bids or not asks:
            return 0.0
        mid = (bids[0][0] + asks[0][0]) / 2
        return abs(avg_fill - mid) / mid if mid > 0 else 0.0

    def analyze_symbol(self, symbol: str, market_data: Dict[str, Any]) -> SignalResult:
        klines_1m = self.client.get_klines(symbol, '1m', limit=max(20, self.cvd_window + 1))
        order_book = self.client.get_order_book(symbol, limit=10)
        trades = self.client.get_recent_trades(symbol, limit=max(50, self.cvd_window * 10))

        if not klines_1m or not order_book:
            return SignalResult('NEUTRAL', 0.0, 'Veri yetersiz', self.name)

        current_price = market_data.get('current_price') or klines_1m[-1]['close']

        vwap = self._calc_vwap(klines_1m)
        atr = self._calc_atr1m(klines_1m)
        cvd = self._calc_cvd(trades)
        obi = self._calc_obi(order_book)
        spread_bps, best_bid, best_ask = self._calc_spread_bps(order_book)

        last3_high = max(k['high'] for k in klines_1m[-3:]) if len(klines_1m) >= 3 else klines_1m[-1]['high']
        last3_low = min(k['low'] for k in klines_1m[-3:]) if len(klines_1m) >= 3 else klines_1m[-1]['low']
        close_last = klines_1m[-1]['close']

        est_slippage_pct_buy = self._estimate_slippage_pct(amount=filled_amount_placeholder(klines_1m, current_price), side='BUY', order_book=order_book)
        est_slippage_pct_sell = self._estimate_slippage_pct(amount=filled_amount_placeholder(klines_1m, current_price), side='SELL', order_book=order_book)

        if atr <= 0 or (atr / current_price) < 0.0005:
            return SignalResult('NEUTRAL', 0.0, 'ATR düşük', self.name, {
                'vwap': vwap, 'atr': atr, 'cvd': cvd, 'obi': obi, 'spread_bps': spread_bps
            })

        long_rules = [
            current_price >= vwap * (1 - self.vwap_tolerance_pct),
            close_last > last3_high,
            obi > self.obi_threshold,
            cvd > 0,
            spread_bps < self.max_spread_bps,
            est_slippage_pct_buy < self.max_slippage_pct
        ]

        short_rules = [
            current_price <= vwap * (1 + self.vwap_tolerance_pct),
            close_last < last3_low,
            obi < -self.obi_threshold,
            cvd < 0,
            spread_bps < self.max_spread_bps,
            est_slippage_pct_sell < self.max_slippage_pct
        ]

        action = 'NEUTRAL'
        confidence = 0.0
        reason = 'Koşullar sağlanmadı'

        rules_passed_long = sum(1 for r in long_rules if r)
        rules_passed_short = sum(1 for r in short_rules if r)

        if rules_passed_long >= 5 and rules_passed_long > rules_passed_short:
            action = 'LONG'
            confidence = min(1.0, 0.6 + 0.05 * (rules_passed_long - 5))
            reason = f"Long koşulları: {rules_passed_long}/6"
        elif rules_passed_short >= 5 and rules_passed_short > rules_passed_long:
            action = 'SHORT'
            confidence = min(1.0, 0.6 + 0.05 * (rules_passed_short - 5))
            reason = f"Short koşulları: {rules_passed_short}/6"

        metadata = {
            'vwap': vwap,
            'atr': atr,
            'cvd': cvd,
            'obi': obi,
            'spread_bps': spread_bps,
            'best_bid': best_bid,
            'best_ask': best_ask,
            'last3_high': last3_high,
            'last3_low': last3_low,
            'vwap_tol_pct': self.vwap_tolerance_pct,
            'atr_mult_sl': self.atr_multiplier_sl,
            'est_slippage_buy_pct': est_slippage_pct_buy,
            'est_slippage_sell_pct': est_slippage_pct_sell,
        }

        return SignalResult(action=action, confidence=confidence, reason=reason, strategy_name=self.name, metadata=metadata)


def filled_amount_placeholder(klines_1m: List[Dict[str, Any]], current_price: float) -> float:
    if not klines_1m:
        return 0.0
    last_vol = klines_1m[-1]['volume']
    return max(0.0, (last_vol * 0.001))


