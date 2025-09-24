"""
키움증권 WebSocket을 통한 실시간 데이터 스트리밍
- 실시간 체결 (0B: 주식체결)
- 실시간 호가 (0C: 주식우선호가, 0D: 주식호가잔량)
- 실시간 주문체결 (00: 주문체결)
"""

import asyncio
import websockets
import json
import threading
from typing import List, Callable, Optional, Dict
from config import BASE_URL
from auth import get_access_token


class KiwoomWebSocketStreamer:
    """
    키움증권 WebSocket을 통해 실시간 데이터를 구독하는 클래스
    """

    def __init__(self, symbols: List[str]):
        """
        :param symbols: 구독할 종목 코드 리스트 (예: ["005930", "069500"])
        """
        # WebSocket URL 생성
        if "mockapi" in BASE_URL:
            self.ws_url = "wss://mockapi.kiwoom.com:10000/api/dostk/websocket"
        else:
            self.ws_url = "wss://api.kiwoom.com:10000/api/dostk/websocket"
            
        self.symbols = symbols
        self.websocket = None
        self.connected = False
        self.keep_running = True
        
        # 콜백 함수들
        self.on_tick: Optional[Callable[[str, int], None]] = None       # 콜백: (symbol: str, price: int) -> None
        self.on_orderbook: Optional[Callable[[str, list, list], None]] = None  # 콜백: (symbol: str, bids: list, asks: list) -> None
        self.on_order_execution: Optional[Callable[[Dict], None]] = None  # 주문체결 콜백

    async def connect(self):
        """WebSocket 서버에 연결"""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            self.connected = True
            print("[키움 WebSocket 연결 성공]")

            # 로그인 패킷 전송
            login_packet = {
                'trnm': 'LOGIN',
                'token': get_access_token()
            }
            
            print("[키움 WebSocket 로그인 패킷 전송]")
            await self.send_message(login_packet)

        except Exception as e:
            print(f"[키움 WebSocket 연결 오류] {e}")
            self.connected = False

    async def send_message(self, message: Dict):
        """서버에 메시지 전송"""
        if not self.connected:
            await self.connect()
            
        if self.connected:
            message_str = json.dumps(message)
            await self.websocket.send(message_str)
            print(f"[키움 WebSocket 메시지 전송] {message_str}")

    async def receive_messages(self):
        """서버로부터 메시지 수신"""
        while self.keep_running and self.connected:
            try:
                response = json.loads(await self.websocket.recv())
                await self.handle_message(response)
                
            except websockets.ConnectionClosed:
                print("[키움 WebSocket 연결 종료됨]")
                self.connected = False
                break
            except Exception as e:
                print(f"[키움 WebSocket 수신 오류] {e}")

    async def handle_message(self, response: Dict):
        """수신된 메시지 처리"""
        trnm = response.get('trnm')
        
        # 로그인 응답 처리
        if trnm == 'LOGIN':
            return_code = response.get('return_code', -1)
            return_msg = response.get('return_msg', '')
            
            if return_code != 0:
                print(f"[키움 WebSocket 로그인 실패] {return_msg}")
                await self.disconnect()
            else:
                print("[키움 WebSocket 로그인 성공]")
                # 로그인 성공 후 실시간 데이터 등록
                await self.register_realtime_data()
        
        # PING 응답 처리
        elif trnm == 'PING':
            await self.send_message(response)  # PING 그대로 응답
        
        # 실시간 데이터 수신
        elif trnm == 'REAL':
            await self.handle_realtime_data(response)
        
        # 등록 응답
        elif trnm == 'REG':
            return_code = response.get('return_code', -1)
            if return_code == 0:
                print("[키움 WebSocket 실시간 등록 성공]")
            else:
                print(f"[키움 WebSocket 실시간 등록 실패] {response.get('return_msg', '')}")

    async def handle_realtime_data(self, response: Dict):
        """실시간 데이터 처리"""
        data_list = response.get('data', [])
        
        for data in data_list:
            data_type = data.get('type')
            item = data.get('item')  # 종목코드
            values = data.get('values', {})
            
            try:
                # 00: 주문체결
                if data_type == '00':
                    if self.on_order_execution:
                        self.on_order_execution(values)
                
                # 0B: 주식체결 (실시간 체결가)
                elif data_type == '0B':
                    current_price = values.get('10')  # 현재가
                    if current_price and self.on_tick:
                        # +/- 부호 제거하고 정수 변환
                        price = int(current_price.replace('+', '').replace('-', ''))
                        self.on_tick(item, price)
                
                # 0C: 주식우선호가 또는 0D: 주식호가잔량
                elif data_type in ['0C', '0D']:
                    if self.on_orderbook:
                        # 키움 호가 데이터 파싱
                        bids = []
                        asks = []
                        
                        # 매수호가 1~5 (values에서 추출)
                        for i in range(1, 6):
                            bid_price = values.get(f'매수호가{i}')
                            bid_qty = values.get(f'매수호가수량{i}')
                            if bid_price and bid_qty:
                                try:
                                    bids.append((int(bid_price), int(bid_qty)))
                                except (ValueError, TypeError):
                                    continue
                        
                        # 매도호가 1~5 (values에서 추출)
                        for i in range(1, 6):
                            ask_price = values.get(f'매도호가{i}')
                            ask_qty = values.get(f'매도호가수량{i}')
                            if ask_price and ask_qty:
                                try:
                                    asks.append((int(ask_price), int(ask_qty)))
                                except (ValueError, TypeError):
                                    continue
                        
                        self.on_orderbook(item, bids, asks)
                        
            except Exception as e:
                print(f"[키움 WebSocket 실시간 데이터 처리 오류] {e}")

    async def register_realtime_data(self):
        """실시간 데이터 등록"""
        # 실시간 항목들 등록
        reg_packet = {
            'trnm': 'REG',
            'grp_no': '1',
            'refresh': '1',  # 기존 등록 유지
            'data': []
        }
        
        # 주문체결 등록 (종목코드 불필요)
        reg_packet['data'].append({
            'item': [''],
            'type': ['00']  # 주문체결
        })
        
        # 각 종목별로 체결, 호가 등록
        for symbol in self.symbols:
            reg_packet['data'].extend([
                {
                    'item': [symbol],
                    'type': ['0B']  # 주식체결
                },
                {
                    'item': [symbol], 
                    'type': ['0C']  # 주식우선호가
                },
                {
                    'item': [symbol],
                    'type': ['0D']  # 주식호가잔량
                }
            ])
        
        await self.send_message(reg_packet)

    async def disconnect(self):
        """WebSocket 연결 종료"""
        self.keep_running = False
        if self.connected and self.websocket:
            await self.websocket.close()
            self.connected = False
            print("[키움 WebSocket 연결 종료]")

    async def run(self):
        """WebSocket 실행"""
        await self.connect()
        if self.connected:
            await self.receive_messages()

    def start(self):
        """
        WebSocket을 별도 스레드에서 시작
        (기존 코드와의 호환성을 위해 유지)
        """
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.run())
            
        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()
        print("[키움 WebSocket 스트리머 시작]")

    def stop(self):
        """
        WebSocket 연결 종료
        (기존 코드와의 호환성을 위해 유지)
        """
        self.keep_running = False
        print("[키움 WebSocket 스트리머 종료 요청]")


# 기존 코드와의 호환성을 위한 별칭
RealTimeStreamer = KiwoomWebSocketStreamer 