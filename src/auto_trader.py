"""
RSI 기반 자동매매 엔진
- 매매 신호 생성 및 자동 주문 실행
- 실시간 웹소켓 데이터와 연동
"""

import time
import threading
from typing import List, Dict, Any
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal

from api import (
    place_market_order_rest, 
    get_daily_candles_rest, 
    get_10min_candles_rest,
    get_orderbook_rest,
    place_limit_order_rest,
    get_holdings_rest
)
from indicators import calculate_rsi as compute_rsi, simple_moving_average, check_daily_uptrend
from websocket_streamer import KiwoomWebSocketStreamer as RealTimeStreamer
from config import (
    DEFAULT_SYMBOLS,
    OVERSOLD_RSI_THRESHOLD, 
    TARGET_PROFIT_FIRST, 
    TARGET_PROFIT_SECOND,
    MAX_ORDERBOOK_LEVELS,
    TR_SLEEP_SHORT
)


class AutoTrader(QObject):
    """
    REST API 기반 자동매매 엔진
    - 10분봉 RSI 과매도 시 호가 스냅샷 기준 지정가 매수
    - 실시간 틱에서 수익률 목표 달성 시 시장가 매도
    """

    sig_signal_msg = pyqtSignal(str)                 # 상태 메시지 시그널
    sig_position_changed = pyqtSignal(str, int, int) # 포지션 변경 시그널

    def __init__(self, symbols: List[str]):
        super().__init__()
        self.symbols = symbols
        self.rts = RealTimeStreamer(symbols)
        self.is_running = False
        self.strategy_thread = None
        
        self.positions = {
            sym: {
                "qty": 0, 
                "avg_price": 0, 
                "buy_orders": [], 
                "first_sold": False, 
                "second_sold": False
            }
            for sym in symbols
        }

        self.oversold_threshold = OVERSOLD_RSI_THRESHOLD
        self.first_target = TARGET_PROFIT_FIRST
        self.second_target = TARGET_PROFIT_SECOND

        self.rts.on_tick = self.on_real_tick
        self.rts.on_orderbook = self.on_orderbook_update

    def start(self):
        """자동매매 시작"""
        if self.is_running:
            self.sig_signal_msg.emit("[자동매매] 이미 실행 중입니다.")
            return
            
        self.is_running = True
        try:
            self.rts.start()
            self.sig_signal_msg.emit("[WebSocket] 실시간 데이터 연결 시도 중...")
        except Exception as e:
            self.sig_signal_msg.emit(f"[WebSocket 오류] {str(e)} - 실시간 데이터 없이 계속 진행")
        
        self.strategy_thread = threading.Thread(target=self.run_strategy, daemon=True)
        self.strategy_thread.start()
        self.sig_signal_msg.emit("[자동매매] 시작되었습니다. (실시간 데이터는 연결 시 활성화)")

    def stop(self):
        """자동매매 중지"""
        if not self.is_running:
            self.sig_signal_msg.emit("[자동매매] 실행 중이 아닙니다.")
            return
            
        self.is_running = False
        try:
            self.rts.stop()
        except Exception as e:
            self.sig_signal_msg.emit(f"[WebSocket 중지 오류] {str(e)}")
        self.sig_signal_msg.emit("[자동매매] 중지되었습니다.")

    def run_strategy(self):
        """전략 실행 루프"""
        while self.is_running:
            try:
                now = datetime.now()
                if ((now.hour > 9) or (now.hour == 9 and now.minute >= 0)) and \
                   ((now.hour < 15) or (now.hour == 15 and now.minute < 25)):
                    
                    for sym in self.symbols:
                        if not self.is_running:
                            break
                        
                        try:
                            df_daily = get_daily_candles_rest(sym, count=30)
                            if df_daily.empty or not check_daily_uptrend(df_daily):
                                continue

                            df_10m = get_10min_candles_rest(sym, count=50)
                            if df_10m.empty or len(df_10m) < 14:
                                continue
                            
                            df_10m['RSI'] = compute_rsi(df_10m['종가'], period=14)
                            latest_rsi = df_10m['RSI'].iloc[-1]

                            if latest_rsi <= self.oversold_threshold:
                                self.trigger_buy(sym)
                                time.sleep(TR_SLEEP_SHORT)

                        except Exception as e:
                            self.sig_signal_msg.emit(f"[{sym} 전략 오류] {str(e)}")
                        
                        time.sleep(TR_SLEEP_SHORT)

                    secs = 60 - datetime.now().second
                    time.sleep(secs if secs > 0 else 0.1)
                else:
                    time.sleep(30)
                    
            except Exception as e:
                self.sig_signal_msg.emit(f"[전략 실행 오류] {str(e)}")
                time.sleep(10)

    def trigger_buy(self, symbol: str):
        """지정가 매수 주문"""
        try:
            pos = self.positions.get(symbol)
            if pos['qty'] > 0 or pos['buy_orders']:
                return

            bids, _ = get_orderbook_rest(symbol)
            if not bids:
                self.sig_signal_msg.emit(f"[매수 실패] {symbol} 호가 정보 없음")
                return
                
            buy_order_ids = []
            for level in range(min(MAX_ORDERBOOK_LEVELS, len(bids))):
                price, _ = bids[level]
                if price and price > 0:
                    res = place_limit_order_rest(symbol, "BUY", 1, price)
                    order_id = res.get("data", {}).get("order_id")
                    if order_id:
                        buy_order_ids.append(order_id)
                    time.sleep(0.1)

            pos['buy_orders'] = buy_order_ids
            self.sig_signal_msg.emit(f"[매수 주문] {symbol} 지정가 매수 요청 완료")
        
        except Exception as e:
            self.sig_signal_msg.emit(f"[매수 주문 오류] {symbol}: {str(e)}")

    def on_orderbook_update(self, symbol: str, bids: list, asks: list):
        """실시간 호가 업데이트"""
        pass

    def on_real_tick(self, symbol: str, price: int):
        """실시간 체결가 업데이트"""
        pos = self.positions.get(symbol)
        qty = pos.get("qty", 0)
        avg_price = pos.get("avg_price", 0)
        if qty <= 0 or avg_price <= 0:
            return

        if (not pos['first_sold']) and (price >= int(avg_price * (1 + self.first_target))):
            sell_qty = qty // 2 if qty > 1 else qty
            if sell_qty > 0:
                res = place_market_order_rest(symbol, "SELL", sell_qty)
                pos['first_sold'] = True
                self.sig_signal_msg.emit(f"[1차 매도] {symbol} 수량={sell_qty}")

        elif pos['first_sold'] and (not pos['second_sold']):
            rem_qty = pos.get("qty", 0)
            if rem_qty > 0 and price >= int(avg_price * (1 + self.second_target)):
                res = place_market_order_rest(symbol, "SELL", rem_qty)
                pos['second_sold'] = True
                self.sig_signal_msg.emit(f"[2차 매도] {symbol} 수량={rem_qty}")

    def on_order_filled(self, order_id: str, symbol: str, side: str, filled_qty: int, filled_price: int):
        """주문 체결 처리"""
        pos = self.positions.get(symbol)
        if not pos:
            return
            
        if side == "BUY":
            prev_qty = pos.get("qty", 0)
            prev_avg = pos.get("avg_price", 0)
            new_qty = prev_qty + filled_qty
            new_avg = filled_price if prev_qty == 0 else (prev_avg * prev_qty + filled_price * filled_qty) // new_qty
            pos['qty'] = new_qty
            pos['avg_price'] = new_avg
            self.sig_position_changed.emit(symbol, new_qty, new_avg)
            self.sig_signal_msg.emit(f"[매수 체결] {symbol} 수량={filled_qty}, 가격={filled_price}")

        elif side == "SELL":
            prev_qty = pos.get("qty", 0)
            new_qty = max(0, prev_qty - filled_qty)
            pos['qty'] = new_qty
            if new_qty == 0:
                pos['avg_price'] = 0
                pos['first_sold'] = False
                pos['second_sold'] = False
                pos['buy_orders'] = []
            self.sig_position_changed.emit(symbol, pos['qty'], pos['avg_price'])
            self.sig_signal_msg.emit(f"[매도 체결] {symbol} 수량={filled_qty}, 가격={filled_price}") 