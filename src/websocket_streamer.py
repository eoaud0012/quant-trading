"""
WebSocket을 통한 실시간 데이터 스트리밍
- 실시간 체결 (틱)
- 실시간 호가
"""

import websocket
import threading
import json
from typing import List, Callable, Optional
from .config import WS_URL
from .auth import access_token


class RealTimeStreamer:
    """
    WebSocket을 통해 실시간 체결(틱)과 호가 5레벨 데이터를 구독하는 클래스
    """

    def __init__(self, symbols: List[str]):
        """
        :param symbols: 구독할 종목 코드 리스트 (예: ["005930", "069500"])
        """
        self.ws_url = WS_URL
        self.symbols = symbols
        self.ws: Optional[websocket.WebSocketApp] = None
        self.on_tick: Optional[Callable[[str, int], None]] = None       # 콜백: (symbol: str, price: int) -> None
        self.on_orderbook: Optional[Callable[[str, list, list], None]] = None  # 콜백: (symbol: str, bids: list, asks: list) -> None
        self.is_running = False

    def _on_open(self, ws):
        """
        WebSocket 연결이 열리면 호출되는 콜백
        """
        print("[WebSocket 연결 성공]")
        sub_msg = {
            "type": "subscribe",
            "channels": []
        }
        for sym in self.symbols:
            sub_msg["channels"].append({"name": "ticker", "symbols": [sym]})
            sub_msg["channels"].append({"name": "orderbook", "symbols": [sym]})
        
        ws.send(json.dumps(sub_msg))
        print(f"[WebSocket 구독 요청] 종목: {self.symbols}")

    def _on_message(self, ws, message):
        """
        WebSocket 메시지를 수신하면 호출되는 콜백
        """
        try:
            data = json.loads(message)
            channel = data.get("channel")
            symbol = data.get("symbol")

            if channel == "ticker":
                # 체결가 빈도(틱) 업데이트
                price = data.get("trade_price")
                if self.on_tick and price is not None:
                    self.on_tick(symbol, price)

            elif channel == "orderbook":
                # 호가 5레벨 업데이트
                units = data.get("orderbook_units", [])
                bids = [(unit["bid_price"], unit["bid_size"]) for unit in units]
                asks = [(unit["ask_price"], unit["ask_size"]) for unit in units]
                if self.on_orderbook:
                    self.on_orderbook(symbol, bids, asks)
                    
        except Exception as e:
            print(f"[WebSocket 메시지 처리 오류] {str(e)}")

    def _on_error(self, ws, error):
        print(f"[WebSocket Error] {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        print(f"[WebSocket Closed] code={close_status_code}, msg={close_msg}")
        self.is_running = False

    def start(self):
        """
        WebSocket 연결을 시작하고, 별도 쓰레드에서 메시지를 수신
        """
        if self.is_running:
            print("[WebSocket 이미 실행 중]")
            return
            
        headers = [f"Authorization: Bearer {access_token}"]
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            header=headers,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        
        self.is_running = True
        # daemon=True: 메인 스레드 종료 시 백그라운드도 자동 종료
        thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        thread.start()
        print("[WebSocket 스트리머 시작]")

    def stop(self):
        """
        WebSocket 연결 종료
        """
        if self.ws and self.is_running:
            self.is_running = False
            self.ws.close()
            print("[WebSocket 스트리머 종료]") 