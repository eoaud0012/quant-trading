"""
PyQt5 기반 미니 HTS GUI
- 보유 종목 현황 표시
- 자동매매 ON/OFF 제어
- 실시간 상태 메시지 표시
- 실시간 10분봉 캔들스틱 차트 + RSI 지표
- 종목 검색 및 종목명 표시
"""

import sys
from collections import deque
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QLineEdit, QCompleter
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
import pyqtgraph as pg
from pyqtgraph import GraphicsObject

from api import get_holdings_rest, get_market_data_rest
from auto_trader import AutoTrader
from auth import initialize_auth
from stock_master import get_all_stock_dict, search_stocks_comprehensive


# 전체 종목 딕셔너리 (시작 시 로드)
ALL_STOCK_DICT = None

def get_stock_name(code):
    """종목코드로 종목명 조회 (전체 종목 데이터베이스 사용)"""
    global ALL_STOCK_DICT
    if ALL_STOCK_DICT is None:
        ALL_STOCK_DICT = get_all_stock_dict()
    
    return ALL_STOCK_DICT.get(code, code)

def search_stocks(query):
    """종목 검색 (전체 종목 데이터베이스 사용)"""
    global ALL_STOCK_DICT
    if ALL_STOCK_DICT is None:
        ALL_STOCK_DICT = get_all_stock_dict()
    
    return search_stocks_comprehensive(query, ALL_STOCK_DICT)


def compute_rsi_simple(prices, period=14):
    """
    간단한 RSI 계산 함수 (리스트 입력 가능)
    """
    if len(prices) < period + 1:
        return []
    
    prices = pd.Series(prices)
    delta = prices.diff(1)
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)

    roll_up = up.rolling(window=period).mean()
    roll_down = down.rolling(window=period).mean()
    
    rs = roll_up / roll_down.replace(0, 1e-10)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    
    return rsi.dropna().tolist()


class CandlestickItem(GraphicsObject):
    """캔들스틱 차트 아이템"""
    
    def __init__(self, data):
        GraphicsObject.__init__(self)
        self.data = data  # [(time, open, high, low, close, volume), ...]
        self.generatePicture()
    
    def generatePicture(self):
        """캔들스틱 그래픽 생성"""
        self.picture = pg.QtGui.QPicture()
        p = pg.QtGui.QPainter(self.picture)
        
        w = 0.8  # 캔들 폭
        
        for i, (t, o, h, l, c, v) in enumerate(self.data):
            # 캔들 색상 결정 (상승: 빨강, 하락: 파랑)
            if c > o:  # 상승
                p.setPen(pg.mkPen('r'))
                p.setBrush(pg.mkBrush('r'))
            else:  # 하락
                p.setPen(pg.mkPen('b'))
                p.setBrush(pg.mkBrush('b'))
            
            # 고가-저가 라인 그리기
            p.drawLine(pg.QtCore.QPointF(i, l), pg.QtCore.QPointF(i, h))
            
            # 캔들 몸통 그리기
            body_height = abs(c - o)
            body_bottom = min(o, c)
            
            if body_height > 0:
                p.drawRect(pg.QtCore.QRectF(i - w/2, body_bottom, w, body_height))
            else:
                # 도지 캔들 (시가=종가)
                p.drawLine(pg.QtCore.QPointF(i - w/2, o), pg.QtCore.QPointF(i + w/2, o))
        
        p.end()
    
    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)
    
    def boundingRect(self):
        return pg.QtCore.QRectF(self.picture.boundingRect())
    
    def updateData(self, data):
        """데이터 업데이트"""
        self.data = data
        self.generatePicture()
        self.update()


class RealTimeChart(QWidget):
    """실시간 10분봉 캔들스틱 차트 + RSI 지표 위젯"""
    
    def __init__(self, symbol: str):
        super().__init__()
        self.symbol = symbol
        self.stock_name = get_stock_name(symbol)
        
        # 동적 캔들 관리
        self.base_candles = 50  # 기본 캔들 개수
        self.max_candles = 500  # 최대 캔들 개수 (확장 가능)
        self.current_zoom_level = 1.0  # 현재 줌 레벨
        
        # 10분봉 데이터: [(time, open, high, low, close, volume), ...]
        self.candle_data = []
        self.extended_data = []  # 확장된 과거 데이터
        self.current_candle = None
        self.last_update_time = None
        
        # 한국 주식 시장 시간 설정
        self.market_open = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        self.market_close = datetime.now().replace(hour=15, minute=30, second=0, microsecond=0)
        
        # 토큰 초기화 (필수!)
        try:
            initialize_auth()
            print(f"[차트] {self.symbol}({self.stock_name}) 토큰 초기화 완료")
        except Exception as e:
            print(f"[차트] 토큰 초기화 오류: {e}")
        
        self._init_ui()
        self._init_timer()
    
    def get_market_10min_slots(self, date):
        """특정 날짜의 시장 시간 내 10분봉 슬롯 생성 (9:00-15:30)"""
        slots = []
        current = datetime.combine(date.date(), datetime.min.time().replace(hour=9, minute=0))
        end_time = datetime.combine(date.date(), datetime.min.time().replace(hour=15, minute=30))
        
        while current <= end_time:
            # 점심시간 (12:00-13:00) 제외
            if not (current.hour == 12):
                slots.append(current)
            current += timedelta(minutes=10)
        
        return slots
    
    def is_market_time(self, dt):
        """주식 시장 시간인지 확인 (9:00-15:30, 점심시간 제외)"""
        if dt.hour < 9 or dt.hour > 15:
            return False
        if dt.hour == 15 and dt.minute > 30:
            return False
        if dt.hour == 12:  # 점심시간 제외
            return False
        return True
    
    def generate_extended_historical_data(self, days_back=5):
        """확장된 과거 데이터 생성 (여러 일자의 시장 시간 기준)"""
        print(f"[확장데이터] {days_back}일간의 시장시간 10분봉 생성 시작...")
        
        # 종목별 적절한 기준 가격 설정
        stock_prices = {
            "005930": 58000,    # 삼성전자
            "000660": 120000,   # SK하이닉스  
            "035420": 190000,   # NAVER
            "373220": 400000,   # LG에너지솔루션
            "005380": 170000,   # 현대차
            "068270": 180000,   # 셀트리온
            "035720": 50000,    # 카카오
            "051910": 350000,   # LG화학
        }
        
        base_price = stock_prices.get(self.symbol, 50000)
        extended_data = []
        time_index = 0
        
        # 과거 여러 일자 데이터 생성
        for day_offset in range(days_back, 0, -1):
            target_date = datetime.now() - timedelta(days=day_offset)
            
            # 주말 제외
            if target_date.weekday() >= 5:  # 토요일(5), 일요일(6)
                continue
            
            # 해당 날짜의 시장 시간 10분봉 슬롯
            market_slots = self.get_market_10min_slots(target_date)
            daily_start_price = base_price
            
            print(f"[확장데이터] {target_date.strftime('%Y-%m-%d')} ({len(market_slots)}개 10분봉)")
            
            for slot_time in market_slots:
                import random
                
                # 일중 변화율 (±0.5%)
                max_change_rate = 0.005
                change_amount = base_price * random.uniform(-max_change_rate, max_change_rate)
                
                # 시가
                open_price = max(5000, base_price + change_amount)
                
                # 종가 (시가에서 ±0.3% 변화)
                close_change_rate = random.uniform(-0.003, 0.003)
                close_price = max(5000, open_price * (1 + close_change_rate))
                
                # 고가, 저가
                base_high = max(open_price, close_price)
                base_low = min(open_price, close_price)
                
                high_extra = random.uniform(0, 0.002)  # 최대 0.2% 추가
                low_extra = random.uniform(0, 0.002)   # 최대 0.2% 감소
                
                high_price = base_high * (1 + high_extra)
                low_price = max(3000, base_low * (1 - low_extra))
                
                # 가격 검증
                open_price = max(5000, abs(open_price))
                high_price = max(5000, abs(high_price))
                low_price = max(3000, abs(low_price))
                close_price = max(5000, abs(close_price))
                
                # 논리적 순서 보장
                low_price = min(low_price, open_price, close_price)
                high_price = max(high_price, open_price, close_price)
                
                # 거래량 (시간대별 차등)
                if slot_time.hour == 9:  # 개장 직후 높은 거래량
                    volume = random.randint(50000, 200000)
                elif slot_time.hour >= 14:  # 장마감 전 높은 거래량
                    volume = random.randint(30000, 150000)
                else:  # 일반 시간대
                    volume = random.randint(10000, 80000)
                
                extended_data.append((time_index, open_price, high_price, low_price, close_price, volume))
                
                base_price = close_price
                time_index += 1
            
            # 일간 마감 후 다음날을 위한 가격 조정 (±1% 갭)
            gap_change = random.uniform(-0.01, 0.01)
            base_price = max(5000, base_price * (1 + gap_change))
        
        self.extended_data = extended_data
        print(f"[확장데이터] 총 {len(extended_data)}개 10분봉 생성 완료")
        print(f"[시간범위] {extended_data[0][0] if extended_data else 0} ~ {extended_data[-1][0] if extended_data else 0}")
        
        return extended_data
    
    def get_visible_data_for_zoom(self, zoom_level):
        """줌 레벨에 따른 가시 데이터 범위 결정"""
        if zoom_level <= 1.0:
            # 줌인 상태: 기본 캔들 수
            return self.candle_data[-self.base_candles:]
        elif zoom_level <= 2.0:
            # 중간 줌아웃: 기본의 2배
            extended_count = min(self.base_candles * 2, len(self.extended_data))
            return (self.extended_data + self.candle_data)[-extended_count:]
        else:
            # 완전 줌아웃: 모든 확장 데이터
            return self.extended_data + self.candle_data
    
    def detect_zoom_level(self):
        """현재 차트의 줌 레벨 감지"""
        if not self.candle_data:
            return 1.0
        
        # ViewBox의 현재 X축 범위 가져오기
        view_range = self.price_viewbox.viewRange()[0]  # [xMin, xMax]
        current_x_range = view_range[1] - view_range[0]
        
        # 기본 데이터 범위와 비교
        if len(self.candle_data) > 0:
            base_range = len(self.candle_data)
            zoom_level = current_x_range / base_range
            
            # 줌 레벨 업데이트
            if abs(zoom_level - self.current_zoom_level) > 0.2:  # 20% 이상 변화 시
                self.current_zoom_level = zoom_level
                print(f"[줌감지] 줌 레벨 변화: {zoom_level:.2f}")
                
                # 줌아웃 시 확장 데이터 생성/업데이트
                if zoom_level > 1.5 and len(self.extended_data) == 0:
                    self.generate_extended_historical_data()
                    self.update_chart_display()
                elif zoom_level > 2.0 and len(self.extended_data) < 200:
                    # 더 많은 과거 데이터 필요
                    self.generate_extended_historical_data(days_back=10)
                    self.update_chart_display()
        
        return self.current_zoom_level
        
    def generate_sample_data(self):
        """현재 시장시간 기준 샘플 10분봉 데이터 생성"""
        print(f"[현재데이터] 오늘 시장시간 10분봉 생성 시작...")
        
        # 종목별 적절한 기준 가격 설정
        stock_prices = {
            "005930": 58000,    # 삼성전자
            "000660": 120000,   # SK하이닉스  
            "035420": 190000,   # NAVER
            "373220": 400000,   # LG에너지솔루션
            "005380": 170000,   # 현대차
            "068270": 180000,   # 셀트리온
            "035720": 50000,    # 카카오
            "051910": 350000,   # LG화학
        }
        
        base_price = stock_prices.get(self.symbol, 50000)
        self.candle_data = []
        
        # 오늘 날짜의 시장 시간 10분봉
        today = datetime.now()
        market_slots = self.get_market_10min_slots(today)
        
        # 현재 시간까지의 슬롯만 사용 (과거 데이터)
        current_time = datetime.now()
        past_slots = [slot for slot in market_slots if slot <= current_time]
        
        # 최근 20개 정도만 사용 (너무 많으면 초기 로딩이 느림)
        recent_slots = past_slots[-20:] if len(past_slots) > 20 else past_slots
        
        time_index = 0
        for slot_time in recent_slots:
            import random
            
            # 변화율을 작게 제한 (±1%)
            max_change_rate = 0.01
            change_amount = base_price * random.uniform(-max_change_rate, max_change_rate)
            
            # 시가
            open_price = max(5000, base_price + change_amount)
            
            # 종가 (시가에서 ±0.5% 변화)
            close_change_rate = random.uniform(-0.005, 0.005)
            close_price = max(5000, open_price * (1 + close_change_rate))
            
            # 고가, 저가
            base_high = max(open_price, close_price)
            base_low = min(open_price, close_price)
            
            high_extra = random.uniform(0, 0.003)
            low_extra = random.uniform(0, 0.003)
            
            high_price = base_high * (1 + high_extra)
            low_price = max(3000, base_low * (1 - low_extra))
            
            # 가격 검증
            open_price = max(5000, abs(open_price))
            high_price = max(5000, abs(high_price))
            low_price = max(3000, abs(low_price))
            close_price = max(5000, abs(close_price))
            
            # 논리적 순서 보장
            low_price = min(low_price, open_price, close_price)
            high_price = max(high_price, open_price, close_price)
            
            # 시간대별 거래량
            if slot_time.hour == 9:
                volume = random.randint(50000, 200000)
            elif slot_time.hour >= 14:
                volume = random.randint(30000, 150000)
            else:
                volume = random.randint(10000, 80000)
            
            self.candle_data.append((time_index, open_price, high_price, low_price, close_price, volume))
            base_price = close_price
            time_index += 1
        
        print(f"[현재데이터] 오늘 {len(self.candle_data)}개 10분봉 생성 완료")
        if self.candle_data:
            print(f"[가격범위] 최저: {min([c[3] for c in self.candle_data]):,.0f}원, 최고: {max([c[2] for c in self.candle_data]):,.0f}원")
            print(f"[시간범위] {self.candle_data[0][0]} ~ {self.candle_data[-1][0]} (모두 양수)")
        
        # 초기 확장 데이터도 생성 (백그라운드)
        QTimer.singleShot(1000, lambda: self.generate_extended_historical_data())
    
    def update_chart_display(self):
        """차트 화면 업데이트 (줌 레벨에 따른 동적 데이터)"""
        # 현재 줌 레벨 감지
        zoom_level = self.detect_zoom_level()
        
        # 줌 레벨에 따른 데이터 선택
        display_data = self.get_visible_data_for_zoom(zoom_level)
        
        if not display_data:
            return
        
        # 가격 차트 업데이트
        if self.candlestick_item:
            self.price_widget.removeItem(self.candlestick_item)
        
        self.candlestick_item = CandlestickItem(display_data)
        self.price_widget.addItem(self.candlestick_item)
        
        # X축과 Y축 범위 설정
        if len(display_data) > 0:
            # X축 범위 (시간) - 항상 양수 보장
            times = [candle[0] for candle in display_data]
            x_min = max(0, min(times))
            x_max = max(times)
            x_range = x_max - x_min
            
            # X축 여백 추가
            x_margin = max(1, x_range * 0.02)  # 2% 여백
            x_min_display = max(0, x_min - x_margin)
            x_max_display = x_max + x_margin
            
            # Y축 범위 (가격)
            all_highs = [candle[2] for candle in display_data]
            all_lows = [candle[3] for candle in display_data]
            
            min_price = min(all_lows)
            max_price = max(all_highs)
            price_range = max_price - min_price
            
            # Y축 여백 계산
            margin_rate = max(0.03, min(0.08, price_range / max_price))
            margin = price_range * margin_rate
            
            y_min = max(0, min_price - margin)
            y_max = max_price + margin
            
            # 너무 작은 범위 방지
            if (y_max - y_min) / y_max < 0.03:
                center = (y_max + y_min) / 2
                range_half = center * 0.015
                y_min = max(0, center - range_half)
                y_max = center + range_half
            
            # ViewBox 제한 설정 (확장된 데이터에 맞게)
            self.price_viewbox.setLimits(
                xMin=0,
                xMax=x_max_display * 1.5,
                yMin=0,
                yMax=y_max * 1.5,
                minXRange=max(1, x_range * 0.05),
                minYRange=(y_max - y_min) * 0.05
            )
            
            # 줌 상태가 크게 변하지 않은 경우에만 범위 설정
            if abs(zoom_level - 1.0) < 0.1:  # 기본 줌 상태일 때만
                self.price_widget.setXRange(x_min_display, x_max_display, padding=0)
                self.price_widget.setYRange(y_min, y_max, padding=0)
            
            # RSI와 거래량 차트 X축 동기화
            self.rsi_viewbox.setLimits(
                xMin=0,
                xMax=x_max_display * 1.5,
                yMin=0,
                yMax=100,
                minXRange=max(1, x_range * 0.05)
            )
            
            self.volume_viewbox.setLimits(
                xMin=0,
                xMax=x_max_display * 1.5,
                yMin=0,
                minXRange=max(1, x_range * 0.05)
            )
        
        # RSI 차트 업데이트 (확장된 데이터 기준)
        if len(display_data) >= 14:
            closes = [candle[4] for candle in display_data]
            rsi_values = compute_rsi_simple(closes, period=14)
            
            if len(rsi_values) >= 2:
                rsi_start_idx = len(display_data) - len(rsi_values)
                x_data = [display_data[rsi_start_idx + i][0] for i in range(len(rsi_values))]
                x_data = [max(0, x) for x in x_data]
                
                self.rsi_line.setData(x_data, rsi_values)
        
        # 거래량 차트 업데이트
        self.volume_widget.clear()
        if len(display_data) > 0:
            for candle in display_data:
                time_idx, open_p, high_p, low_p, close_p, volume = candle
                time_idx = max(0, time_idx)
                
                # 상승/하락 색상
                color = 'red' if close_p >= open_p else 'blue'
                bg = pg.BarGraphItem(x=[time_idx], height=[volume], width=0.8, brush=color)
                self.volume_widget.addItem(bg)
        
        print(f"[차트업데이트] 줌레벨 {zoom_level:.2f}, 데이터 {len(display_data)}개, X축: {x_min_display:.1f}~{x_max_display:.1f}")
    
    def reset_zoom(self):
        """줌 상태 초기화"""
        if len(self.candle_data) > 0:
            # 기본 데이터 범위로 복원
            display_data = self.candle_data
            
            times = [max(0, candle[0]) for candle in display_data]
            prices = []
            for candle in display_data:
                prices.extend([candle[2], candle[3]])
            
            x_min, x_max = min(times), max(times)
            y_min, y_max = min(prices), max(prices)
            
            x_range = x_max - x_min
            y_range = y_max - y_min
            
            x_margin = max(1, x_range * 0.05)
            y_margin = y_range * 0.05
            
            self.price_widget.setXRange(x_min - x_margin, x_max + x_margin, padding=0)
            self.price_widget.setYRange(max(0, y_min - y_margin), y_max + y_margin, padding=0)
            
            # 줌 레벨 초기화
            self.current_zoom_level = 1.0
            
            print(f"[줌리셋] 기본 범위로 복원: X({x_min}~{x_max}), Y({y_min:.0f}~{y_max:.0f})")
    
    def _init_ui(self):
        """차트 UI 초기화"""
        layout = QVBoxLayout(self)
        
        # 종목 검색 및 선택 영역
        search_layout = QHBoxLayout()
        
        # 종목 검색 입력창
        search_label = QLabel("종목 검색:")
        search_label.setFont(QFont("Arial", 10, QFont.Bold))
        search_layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("종목코드 또는 종목명 입력 (예: 005930, 삼성전자)")
        self.search_input.setMaximumWidth(300)
        self.search_input.returnPressed.connect(self.search_and_select_stock)
        search_layout.addWidget(self.search_input)
        
        # 검색 버튼
        search_btn = QPushButton("검색")
        search_btn.setMaximumWidth(60)
        search_btn.clicked.connect(self.search_and_select_stock)
        search_layout.addWidget(search_btn)
        
        # 빠른 선택 콤보박스
        quick_label = QLabel("빠른선택:")
        quick_label.setFont(QFont("Arial", 10, QFont.Bold))
        search_layout.addWidget(quick_label)
        
        self.symbol_combo = QComboBox()
        popular_stocks = [
            ("005930", "삼성전자"), ("000660", "SK하이닉스"), ("035420", "NAVER"), 
            ("373220", "LG에너지솔루션"), ("005380", "현대차"), ("068270", "셀트리온"),
            ("069500", "KODEX 200"), ("096770", "SK이노베이션"), ("003490", "대한항공")
        ]
        
        for code, name in popular_stocks:
            self.symbol_combo.addItem(f"{code} ({name})", code)
        
        # 현재 종목으로 설정
        current_display = f"{self.symbol} ({self.stock_name})"
        combo_index = self.symbol_combo.findText(current_display)
        if combo_index >= 0:
            self.symbol_combo.setCurrentIndex(combo_index)
        
        self.symbol_combo.currentIndexChanged.connect(self.on_combo_changed)
        self.symbol_combo.setMaximumWidth(200)
        search_layout.addWidget(self.symbol_combo)
        
        # 줌 리셋 버튼 추가
        reset_btn = QPushButton("줌 리셋")
        reset_btn.setMaximumWidth(80)
        reset_btn.clicked.connect(self.reset_zoom)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        search_layout.addWidget(reset_btn)
        
        search_layout.addStretch()
        layout.addLayout(search_layout)
        
        # 현재 선택된 종목 표시
        self.current_stock_label = QLabel(f"📈 {self.symbol} - {self.stock_name}")
        self.current_stock_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.current_stock_label.setStyleSheet("""
            background-color: #e3f2fd;
            color: #1565c0;
            border: 2px solid #1976d2;
            border-radius: 8px;
            padding: 8px;
            margin: 5px 0;
        """)
        layout.addWidget(self.current_stock_label)
        
        # PyQtGraph 설정
        pg.setConfigOptions(antialias=True)
        
        # 메인 차트 위젯 (가격 차트) - 상용 HTS 스타일로 개선
        self.price_widget = pg.PlotWidget(title=f"{self.symbol}({self.stock_name}) 실시간 10분봉")
        self.price_widget.setBackground('w')
        self.price_widget.setLabel('left', '가격', color='black')
        self.price_widget.getAxis('left').setPen(pg.mkPen(color='black'))
        self.price_widget.getAxis('bottom').setPen(pg.mkPen(color='black'))
        self.price_widget.getAxis('left').setTextPen(pg.mkPen(color='black'))
        self.price_widget.getAxis('bottom').setTextPen(pg.mkPen(color='black'))
        
        # 상용 HTS 스타일 줌 및 인터랙션 설정 (개선)
        self.price_widget.enableAutoRange(axis='y', enable=False)  # Y축 자동 범위 비활성화 (수동 제어)
        self.price_widget.setMouseEnabled(x=True, y=True)  # 마우스 팬/줌 활성화
        self.price_widget.showGrid(x=True, y=True, alpha=0.3)  # 그리드 표시
        
        # 줌 제한 설정 (ViewBox 접근)
        self.price_viewbox = self.price_widget.getViewBox()
        self.price_viewbox.setLimits(xMin=0, yMin=0)  # X,Y축 최소값을 0으로 제한 (음수 방지)
        
        # 크로스헤어 (십자선) 추가
        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('gray', width=1, style=2))
        self.crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('gray', width=1, style=2))
        self.price_widget.addItem(self.crosshair_v, ignoreBounds=True)
        self.price_widget.addItem(self.crosshair_h, ignoreBounds=True)
        
        # 마우스 이동 시 크로스헤어 업데이트
        self.price_widget.scene().sigMouseMoved.connect(self.update_crosshair)
        
        # 캔들스틱 아이템
        self.candlestick_item = None
        
        # RSI 차트 위젯 - 상용 HTS 스타일로 개선
        self.rsi_widget = pg.PlotWidget(title="RSI (14)")
        self.rsi_widget.setBackground('w')
        self.rsi_widget.setLabel('left', 'RSI', color='black')
        self.rsi_widget.setLabel('bottom', '시간', color='black')
        self.rsi_widget.getAxis('left').setPen(pg.mkPen(color='black'))
        self.rsi_widget.getAxis('bottom').setPen(pg.mkPen(color='black'))
        self.rsi_widget.getAxis('left').setTextPen(pg.mkPen(color='black'))
        self.rsi_widget.getAxis('bottom').setTextPen(pg.mkPen(color='black'))
        self.rsi_widget.setYRange(0, 100)
        self.rsi_widget.setMaximumHeight(200)
        
        # RSI 차트도 줌 및 그리드 활성화 (Y축 범위 제한)
        self.rsi_widget.setMouseEnabled(x=True, y=True)
        self.rsi_widget.showGrid(x=True, y=True, alpha=0.3)
        self.rsi_viewbox = self.rsi_widget.getViewBox()
        self.rsi_viewbox.setLimits(xMin=0, yMin=0, yMax=100)  # X축 음수 방지, RSI는 0-100 범위로 제한
        
        # RSI 기준선 (30, 70)
        self.rsi_widget.addLine(y=70, pen=pg.mkPen('r', style=Qt.DashLine), label='과매수(70)')
        self.rsi_widget.addLine(y=50, pen=pg.mkPen('gray', style=Qt.DotLine), label='중간(50)')
        self.rsi_widget.addLine(y=30, pen=pg.mkPen('b', style=Qt.DashLine), label='과매도(30)')
        
        # RSI 라인
        self.rsi_line = self.rsi_widget.plot(pen=pg.mkPen('purple', width=2), name='RSI')
        
        # 거래량 차트 (하단) - 상용 HTS 스타일로 개선
        self.volume_widget = pg.PlotWidget(title="거래량")
        self.volume_widget.setBackground('w')
        self.volume_widget.setLabel('left', '거래량', color='black')
        self.volume_widget.setMaximumHeight(120)
        self.volume_widget.setMouseEnabled(x=True, y=True)
        self.volume_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # 거래량 차트도 Y축 최소값 제한
        self.volume_viewbox = self.volume_widget.getViewBox()
        self.volume_viewbox.setLimits(xMin=0, yMin=0)  # X,Y축 모두 음수 방지
        
        # 차트 간 X축 연동 (같은 시간 축 사용)
        self.rsi_widget.setXLink(self.price_widget)
        self.volume_widget.setXLink(self.price_widget)
        
        # 차트 레이아웃 (4:2:1 비율)
        layout.addWidget(self.price_widget, 4)
        layout.addWidget(self.rsi_widget, 2)
        layout.addWidget(self.volume_widget, 1)
        
        # 현재가 표시
        self.price_label = QLabel(f"{self.symbol}({self.stock_name}): 데이터 로딩 중...")
        self.price_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.price_label.setAlignment(Qt.AlignCenter)
        self.price_label.setStyleSheet("""
            background-color: #f0f0f0;
            border: 1px solid #ccc;
            border-radius: 5px;
            padding: 5px;
        """)
        layout.addWidget(self.price_label)
    
    def search_and_select_stock(self):
        """종목 검색 및 선택"""
        query = self.search_input.text().strip()
        if not query:
            return
        
        # 검색 실행
        results = search_stocks(query)
        
        if not results:
            # 검색 결과 없음
            self.search_input.setStyleSheet("background-color: #ffebee; border: 1px solid #f44336;")
            QTimer.singleShot(2000, lambda: self.search_input.setStyleSheet(""))
            return
        
        # 첫 번째 결과 선택
        code, name = results[0]
        self.change_symbol(code)
        
        # 검색창 초기화
        self.search_input.clear()
        self.search_input.setStyleSheet("background-color: #e8f5e8; border: 1px solid #4caf50;")
        QTimer.singleShot(1000, lambda: self.search_input.setStyleSheet(""))
    
    def on_combo_changed(self, index):
        """콤보박스 선택 변경"""
        if index >= 0:
            code = self.symbol_combo.itemData(index)
            if code and code != self.symbol:
                self.change_symbol(code)
    
    def change_symbol(self, new_symbol: str):
        """종목 변경"""
        self.symbol = new_symbol
        self.stock_name = get_stock_name(new_symbol)
        self.candle_data = []
        
        # UI 업데이트
        self.current_stock_label.setText(f"📈 {self.symbol} - {self.stock_name}")
        self.price_widget.setTitle(f"{self.symbol}({self.stock_name}) 실시간 10분봉")
        self.price_label.setText(f"{self.symbol}({self.stock_name}): 데이터 로딩 중...")
        
        # 콤보박스도 업데이트
        display_text = f"{self.symbol} ({self.stock_name})"
        combo_index = self.symbol_combo.findText(display_text)
        if combo_index >= 0:
            self.symbol_combo.blockSignals(True)
            self.symbol_combo.setCurrentIndex(combo_index)
            self.symbol_combo.blockSignals(False)
        
        print(f"[차트] 종목 변경: {self.symbol}({self.stock_name})")
        
        # 새 데이터 로드
        self.generate_sample_data()
        self.update_chart_display()
    
    def _init_timer(self):
        """데이터 업데이트 타이머"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_chart_data)
        self.update_timer.start(30000)  # 30초마다 업데이트 (10분봉이므로 자주 확인)
        
        # 초기 데이터 로드
        self.generate_sample_data()
        self.update_chart_display()
        
    def get_10min_timeframe(self, dt):
        """10분 단위로 시간을 맞춤 (예: 14:23 -> 14:20)"""
        minute = (dt.minute // 10) * 10
        return dt.replace(minute=minute, second=0, microsecond=0)
        
    def generate_sample_data(self):
        """샘플 10분봉 데이터 생성 (음수 완전 방지)"""
        now = datetime.now()
        
        # 종목별 적절한 기준 가격 설정 (안전한 범위)
        stock_prices = {
            "005930": 58000,    # 삼성전자
            "000660": 120000,   # SK하이닉스  
            "035420": 190000,   # NAVER
            "373220": 400000,   # LG에너지솔루션
            "005380": 170000,   # 현대차
            "068270": 180000,   # 셀트리온
            "035720": 50000,    # 카카오
            "051910": 350000,   # LG화학
        }
        
        base_price = stock_prices.get(self.symbol, 50000)  # 기본값 50,000원
        
        self.candle_data = []  # 기존 데이터 초기화
        
        for i in range(20):
            # 시간 인덱스는 항상 양수로 보장 (0부터 시작)
            time_index = i
            
            # 10분 간격으로 시간 생성
            time_point = now - timedelta(minutes=(20-i)*10)
            time_point = self.get_10min_timeframe(time_point)
            
            # 매우 안전한 랜덤 캔들 생성 (음수 완전 방지)
            import random
            
            # 변화율을 더 작게 제한 (±1.5%)
            max_change_rate = 0.015
            change_amount = base_price * random.uniform(-max_change_rate, max_change_rate)
            
            # 시가 = 이전 종가에서 작은 변화 (최소 5,000원 보장)
            open_price = max(5000, base_price + change_amount)
            
            # 종가도 시가에서 작은 변화 (±1%)
            close_change_rate = random.uniform(-0.01, 0.01)
            close_price = max(5000, open_price * (1 + close_change_rate))
            
            # 고가는 시가/종가 중 높은 값에서 약간 위 (최대 0.5% 추가)
            base_high = max(open_price, close_price)
            high_extra = random.uniform(0, 0.005)
            high_price = base_high * (1 + high_extra)
            
            # 저가는 시가/종가 중 낮은 값에서 약간 아래 (최대 0.5% 감소, 최소 3,000원)
            base_low = min(open_price, close_price)
            low_extra = random.uniform(0, 0.005)
            low_price = max(3000, base_low * (1 - low_extra))
            
            # 모든 가격이 양수인지 한번 더 확인
            open_price = max(5000, abs(open_price))
            high_price = max(5000, abs(high_price))
            low_price = max(3000, abs(low_price))
            close_price = max(5000, abs(close_price))
            
            # 논리적 순서 확인: low <= open,close <= high
            low_price = min(low_price, open_price, close_price)
            high_price = max(high_price, open_price, close_price)
            
            # 거래량도 적절한 범위로
            volume = random.randint(10000, 200000)
            
            # 시간 인덱스는 항상 양수로 저장
            self.candle_data.append((time_index, open_price, high_price, low_price, close_price, volume))
            base_price = close_price  # 다음 캔들의 기준가로 사용
        
        print(f"[샘플데이터] {self.symbol} 생성완료: {len(self.candle_data)}개")
        print(f"[가격범위] 최저: {min([c[3] for c in self.candle_data]):,.0f}원, 최고: {max([c[2] for c in self.candle_data]):,.0f}원")
        print(f"[시간범위] {self.candle_data[0][0]} ~ {self.candle_data[-1][0]} (모두 양수)")
    
    def update_crosshair(self, pos):
        """크로스헤어 (십자선) 위치 업데이트"""
        if self.price_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.price_widget.getViewBox().mapSceneToView(pos)
            self.crosshair_v.setPos(mouse_point.x())
            self.crosshair_h.setPos(mouse_point.y())
    
    def update_chart_data(self):
        """차트 데이터 업데이트 - 실제 API 데이터 사용"""
        try:
            # 실제 API로 현재가 조회
            market_data = get_market_data_rest(self.symbol)
            
            if market_data and 'stck_prpr' in market_data:
                current_price_str = market_data['stck_prpr']
                if current_price_str and current_price_str != "0":
                    current_price = int(current_price_str.replace('+', '').replace('-', ''))
                    current_time = datetime.now()
                    
                    # 10분 단위로 시간 조정
                    candle_time = self.get_10min_timeframe(current_time)
                    
                    if self.last_update_time != candle_time:
                        # 새로운 10분봉 캔들 시작
                        time_index = len(self.candle_data)
                        
                        # 최대 캔들 수 제한
                        if len(self.candle_data) >= self.max_candles:
                            self.candle_data.pop(0)
                            # 시간 인덱스 재조정
                            for i in range(len(self.candle_data)):
                                old_data = self.candle_data[i]
                                self.candle_data[i] = (i, old_data[1], old_data[2], old_data[3], old_data[4], old_data[5])
                            time_index = len(self.candle_data)
                        
                        # 새 캔들 추가 (시가=종가=현재가로 시작)
                        volume = int(market_data.get('acml_vol', '1000000').replace('+', '').replace('-', ''))
                        self.candle_data.append((time_index, current_price, current_price, current_price, current_price, volume))
                        self.last_update_time = candle_time
                        
                        print(f"[10분봉] {self.symbol} 새 캔들 생성: {current_price:,}원 ({candle_time.strftime('%H:%M')})")
                    else:
                        # 기존 캔들 업데이트 (고가, 저가, 종가 갱신)
                        if self.candle_data:
                            last_candle = list(self.candle_data[-1])
                            time_idx, open_p, high_p, low_p, close_p, vol = last_candle
                            
                            # 고가, 저가 업데이트
                            new_high = max(high_p, current_price)
                            new_low = min(low_p, current_price)
                            new_volume = int(market_data.get('acml_vol', str(vol)).replace('+', '').replace('-', ''))
                            
                            # 캔들 업데이트
                            self.candle_data[-1] = (time_idx, open_p, new_high, new_low, current_price, new_volume)
                            
                            print(f"[10분봉] {self.symbol} 캔들 업데이트: {current_price:,}원")
                    
                    # 차트 화면 업데이트
                    self.update_chart_display()
                    self.update_price_label(current_price, market_data)
                    
                    return  # API 데이터 사용 성공
                    
            print(f"[10분봉] {self.symbol} API 데이터 없음, 샘플 데이터 사용")
            
        except Exception as e:
            print(f"[10분봉 API 오류] {str(e)}")
        
        # API 실패 시 샘플 데이터 사용
        self.add_sample_candle()
        self.update_chart_display()
    
    def add_sample_candle(self):
        """샘플 캔들 하나 추가 (음수 완전 방지)"""
        if len(self.candle_data) > 0:
            last_candle = self.candle_data[-1]
            import random
            
            # 시간 인덱스는 마지막 캔들의 다음 번호 (항상 양수)
            time_point = max(0, last_candle[0] + 1)
            prev_close = last_candle[4]  # 이전 종가
            
            # 매우 안전한 변화율로 제한 (±1%)
            max_change_rate = 0.01
            change_amount = prev_close * random.uniform(-max_change_rate, max_change_rate)
            
            # 시가 = 이전 종가 + 작은 변화 (최소 3,000원)
            open_price = max(3000, prev_close + change_amount)
            
            # 종가도 시가에서 작은 변화 (±0.5%)
            close_change_rate = random.uniform(-0.005, 0.005)
            close_price = max(3000, open_price * (1 + close_change_rate))
            
            # 고가, 저가 안전하게 생성
            base_high = max(open_price, close_price)
            base_low = min(open_price, close_price)
            
            high_extra = random.uniform(0, 0.003)  # 최대 0.3% 추가
            low_extra = random.uniform(0, 0.003)   # 최대 0.3% 감소
            
            high_price = base_high * (1 + high_extra)
            low_price = max(2000, base_low * (1 - low_extra))  # 최소 2,000원
            
            # 모든 가격이 양수인지 한번 더 확인
            open_price = max(3000, abs(open_price))
            high_price = max(3000, abs(high_price))
            low_price = max(2000, abs(low_price))
            close_price = max(3000, abs(close_price))
            
            # 논리적 순서 확인
            low_price = min(low_price, open_price, close_price)
            high_price = max(high_price, open_price, close_price)
            
            volume = random.randint(10000, 150000)
            
            # 최대 캔들 수 제한
            if len(self.candle_data) >= self.max_candles:
                self.candle_data.pop(0)
                # 시간 인덱스 재조정 (0부터 다시 시작하여 양수 보장)
                for i in range(len(self.candle_data)):
                    old_data = self.candle_data[i]
                    self.candle_data[i] = (i, old_data[1], old_data[2], old_data[3], old_data[4], old_data[5])
                time_point = len(self.candle_data)
            
            # 시간 인덱스는 항상 양수로 저장
            self.candle_data.append((time_point, open_price, high_price, low_price, close_price, volume))
            
            print(f"[샘플캔들] {self.symbol} 추가: 시간{time_point} 시가{open_price:.0f} 고가{high_price:.0f} 저가{low_price:.0f} 종가{close_price:.0f}")
    
    def update_price_label(self, current_price, market_data):
        """현재가 라벨 업데이트"""
        if len(self.candle_data) >= 2:
            prev_close = self.candle_data[-2][4]
            change = current_price - prev_close
            change_rate = (change / prev_close * 100) if prev_close > 0 else 0
            
            if change > 0:
                color = "red"
                arrow = "▲"
            elif change < 0:
                color = "blue"
                arrow = "▼"
            else:
                color = "black"
                arrow = "-"
            
            # RSI 값 표시
            rsi_value = ""
            if len(self.candle_data) >= 14:
                closes = [candle[4] for candle in self.candle_data[-14:]]
                rsi = compute_rsi_simple(closes)
                if len(rsi) > 0:
                    rsi_value = f" | RSI: {rsi[-1]:.1f}"
            
            self.price_label.setText(
                f"{self.symbol}({self.stock_name}): {current_price:,}원 {arrow} {change:+,.0f}원 ({change_rate:+.2f}%){rsi_value}"
            )
            self.price_label.setStyleSheet(f"""
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 5px;
                color: {color};
                font-weight: bold;
            """)
        else:
            self.price_label.setText(f"{self.symbol}({self.stock_name}): {current_price:,}원 (실시간 10분봉)")
    
    def update_chart_display(self):
        """차트 화면 업데이트 (줌 레벨에 따른 동적 데이터)"""
        # 현재 줌 레벨 감지
        zoom_level = self.detect_zoom_level()
        
        # 줌 레벨에 따른 데이터 선택
        display_data = self.get_visible_data_for_zoom(zoom_level)
        
        if not display_data:
            return
        
        # 가격 차트 업데이트
        if self.candlestick_item:
            self.price_widget.removeItem(self.candlestick_item)
        
        self.candlestick_item = CandlestickItem(display_data)
        self.price_widget.addItem(self.candlestick_item)
        
        # X축과 Y축 범위 설정
        if len(display_data) > 0:
            # X축 범위 (시간) - 항상 양수 보장
            times = [candle[0] for candle in display_data]
            x_min = max(0, min(times))
            x_max = max(times)
            x_range = x_max - x_min
            
            # X축 여백 추가
            x_margin = max(1, x_range * 0.02)  # 2% 여백
            x_min_display = max(0, x_min - x_margin)
            x_max_display = x_max + x_margin
            
            # Y축 범위 (가격)
            all_highs = [candle[2] for candle in display_data]
            all_lows = [candle[3] for candle in display_data]
            
            min_price = min(all_lows)
            max_price = max(all_highs)
            price_range = max_price - min_price
            
            # Y축 여백 계산
            margin_rate = max(0.03, min(0.08, price_range / max_price))
            margin = price_range * margin_rate
            
            y_min = max(0, min_price - margin)
            y_max = max_price + margin
            
            # 너무 작은 범위 방지
            if (y_max - y_min) / y_max < 0.03:
                center = (y_max + y_min) / 2
                range_half = center * 0.015
                y_min = max(0, center - range_half)
                y_max = center + range_half
            
            # ViewBox 제한 설정 (확장된 데이터에 맞게)
            self.price_viewbox.setLimits(
                xMin=0,
                xMax=x_max_display * 1.5,
                yMin=0,
                yMax=y_max * 1.5,
                minXRange=max(1, x_range * 0.05),
                minYRange=(y_max - y_min) * 0.05
            )
            
            # 줌 상태가 크게 변하지 않은 경우에만 범위 설정
            if abs(zoom_level - 1.0) < 0.1:  # 기본 줌 상태일 때만
                self.price_widget.setXRange(x_min_display, x_max_display, padding=0)
                self.price_widget.setYRange(y_min, y_max, padding=0)
            
            # RSI와 거래량 차트 X축 동기화
            self.rsi_viewbox.setLimits(
                xMin=0,
                xMax=x_max_display * 1.5,
                yMin=0,
                yMax=100,
                minXRange=max(1, x_range * 0.05)
            )
            
            self.volume_viewbox.setLimits(
                xMin=0,
                xMax=x_max_display * 1.5,
                yMin=0,
                minXRange=max(1, x_range * 0.05)
            )
        
        # RSI 차트 업데이트 (확장된 데이터 기준)
        if len(display_data) >= 14:
            closes = [candle[4] for candle in display_data]
            rsi_values = compute_rsi_simple(closes, period=14)
            
            if len(rsi_values) >= 2:
                rsi_start_idx = len(display_data) - len(rsi_values)
                x_data = [display_data[rsi_start_idx + i][0] for i in range(len(rsi_values))]
                x_data = [max(0, x) for x in x_data]
                
                self.rsi_line.setData(x_data, rsi_values)
        
        # 거래량 차트 업데이트
        self.volume_widget.clear()
        if len(display_data) > 0:
            for candle in display_data:
                time_idx, open_p, high_p, low_p, close_p, volume = candle
                time_idx = max(0, time_idx)
                
                # 상승/하락 색상
                color = 'red' if close_p >= open_p else 'blue'
                bg = pg.BarGraphItem(x=[time_idx], height=[volume], width=0.8, brush=color)
                self.volume_widget.addItem(bg)
        
        print(f"[차트업데이트] 줌레벨 {zoom_level:.2f}, 데이터 {len(display_data)}개, X축: {x_min_display:.1f}~{x_max_display:.1f}")
    
    def reset_zoom(self):
        """줌 상태 초기화"""
        if len(self.candle_data) > 0:
            # 기본 데이터 범위로 복원
            display_data = self.candle_data
            
            times = [max(0, candle[0]) for candle in display_data]
            prices = []
            for candle in display_data:
                prices.extend([candle[2], candle[3]])
            
            x_min, x_max = min(times), max(times)
            y_min, y_max = min(prices), max(prices)
            
            x_range = x_max - x_min
            y_range = y_max - y_min
            
            x_margin = max(1, x_range * 0.05)
            y_margin = y_range * 0.05
            
            self.price_widget.setXRange(x_min - x_margin, x_max + x_margin, padding=0)
            self.price_widget.setYRange(max(0, y_min - y_margin), y_max + y_margin, padding=0)
            
            # 줌 레벨 초기화
            self.current_zoom_level = 1.0
            
            print(f"[줌리셋] 기본 범위로 복원: X({x_min}~{x_max}), Y({y_min:.0f}~{y_max:.0f})")


class MiniHTSWindow(QMainWindow):
    """
    PyQt5 기반 "미니 HTS" GUI – REST API 버전
    - 좌측: 실시간 캔들스틱 차트
    - 우측 상단: 보유 종목 테이블
    - 우측 하단: 총 보유 현황, 자동매매 ON/OFF 토글 버튼
    """

    def __init__(self, symbols: list):
        super().__init__()
        self.symbols = symbols
        self.auto_trader = AutoTrader(symbols)

        self.setWindowTitle("키움증권 자동매매 시스템 (실시간 봉차트)")
        self.setGeometry(100, 100, 1600, 1000)
        
        # 스타일 설정
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel {
                color: #333;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:checked {
                background-color: #f44336;
            }
            QTableWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 5px;
            }
        """)

        self._init_ui()
        self._init_timers()
        self._connect_signals()
        
        print("[GUI 초기화 완료] 실시간 봉차트와 함께 시작됩니다.")

    def _init_ui(self):
        """UI 초기화"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # ┌─────────────────────────────────────────┐
        # │ 좌측: 실시간 캔들스틱 차트                │
        # └─────────────────────────────────────────┘
        self.chart_widget = RealTimeChart(self.symbols[0])
        self.chart_widget.setMinimumWidth(700)

        # ┌─────────────────────────────────────────┐
        # │ 우측: 보유 종목 및 제어 패널              │
        # └─────────────────────────────────────────┘
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 우측 상단: 보유 종목 테이블
        holdings_title = QLabel("보유 종목 현황")
        holdings_title.setFont(QFont("Arial", 14, QFont.Bold))
        holdings_title.setAlignment(Qt.AlignLeft)
        right_layout.addWidget(holdings_title)
        
        self.holdings_table = QTableWidget(0, 6)
        self.holdings_table.setHorizontalHeaderLabels([
            "종목코드", "종목명", "보유수량", "평균단가", "현재가", "평가손익"
        ])
        self.holdings_table.verticalHeader().setVisible(False)
        self.holdings_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.holdings_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.holdings_table.horizontalHeader().setStretchLastSection(True)
        self.holdings_table.setAlternatingRowColors(True)
        right_layout.addWidget(self.holdings_table)

        # 우측 하단: 총 보유량, 총 손익, 제어 버튼
        summary_widget = QWidget()
        summary_layout = QVBoxLayout(summary_widget)
        summary_layout.setSpacing(10)
        
        self.total_qty_label = QLabel("총 보유 주수: 0 주")
        self.total_profit_label = QLabel("총 평가손익: 0 원")
        self.total_qty_label.setFont(QFont("Arial", 12))
        self.total_profit_label.setFont(QFont("Arial", 12))
        
        summary_layout.addWidget(self.total_qty_label)
        summary_layout.addWidget(self.total_profit_label)
        
        # 자동매매 토글 버튼
        self.btn_toggle_auto = QPushButton("자동매매 시작")
        self.btn_toggle_auto.setCheckable(True)
        self.btn_toggle_auto.setMinimumHeight(50)
        self.btn_toggle_auto.setFont(QFont("Arial", 12, QFont.Bold))
        self.btn_toggle_auto.clicked.connect(self.toggle_auto_trading)
        summary_layout.addWidget(self.btn_toggle_auto)
        
        right_layout.addWidget(summary_widget)
        right_layout.addStretch()

        # 메인 레이아웃에 추가
        main_layout.addWidget(self.chart_widget, 3)
        main_layout.addWidget(right_widget, 2)
        
        # 상태바
        self.statusBar().showMessage("준비 완료")

    def _init_timers(self):
        """타이머 초기화"""
        # 30초마다 보유 현황 업데이트
        self.timer = QTimer(self)
        self.timer.setInterval(30 * 1000)
        self.timer.timeout.connect(self.update_holdings)
        self.timer.start()

    def _connect_signals(self):
        """시그널 연결"""
        self.auto_trader.sig_signal_msg.connect(self.show_status_message)
        self.auto_trader.sig_position_changed.connect(self.on_position_changed)

    def update_holdings(self):
        """보유 종목 현황 업데이트"""
        try:
            df = get_holdings_rest()
            
            if df.empty:
                self.holdings_table.setRowCount(0)
                self.total_qty_label.setText("총 보유 주수: 0 주 (API 연결 대기 중)")
                self.total_profit_label.setText("총 평가손익: 0 원 (API 연결 대기 중)")
                return

            row_count = len(df)
            self.holdings_table.setRowCount(row_count)
            total_qty, total_profit = 0, 0

            for idx, row in enumerate(df.itertuples()):
                symbol = str(row.종목코드)
                name = get_stock_name(symbol)
                qty = int(row.보유수량)
                avg_price = int(row.매입단가)
                curr_price = int(row.현재가)
                eval_profit = int(row.평가손익)

                total_qty += qty
                total_profit += eval_profit

                # 테이블 아이템 설정
                items = [
                    QTableWidgetItem(symbol),
                    QTableWidgetItem(name),
                    QTableWidgetItem(f"{qty:,}"),
                    QTableWidgetItem(f"{avg_price:,}"),
                    QTableWidgetItem(f"{curr_price:,}"),
                    QTableWidgetItem(f"{eval_profit:,}")
                ]
                
                # 손익에 따른 색상 설정
                if eval_profit > 0:
                    items[5].setForeground(Qt.red)
                elif eval_profit < 0:
                    items[5].setForeground(Qt.blue)

                for col, item in enumerate(items):
                    item.setTextAlignment(Qt.AlignCenter)
                    self.holdings_table.setItem(idx, col, item)

            self.holdings_table.resizeColumnsToContents()
            
            # 총 현황 업데이트
            self.total_qty_label.setText(f"총 보유 주수: {total_qty:,} 주")
            self.total_profit_label.setText(f"총 평가손익: {total_profit:,} 원")
            
            # 총 손익에 따른 색상
            if total_profit > 0:
                self.total_profit_label.setStyleSheet("color: red; font-weight: bold;")
            elif total_profit < 0:
                self.total_profit_label.setStyleSheet("color: blue; font-weight: bold;")
            else:
                self.total_profit_label.setStyleSheet("color: black;")
                
        except Exception as e:
            # API 에러 발생 시에도 GUI는 정상 작동
            self.total_qty_label.setText("총 보유 주수: API 연결 중...")
            self.total_profit_label.setText("총 평가손익: API 연결 중...")
            self.holdings_table.setRowCount(0)
            print(f"[잔고 조회 오류] {str(e)}")

    def on_position_changed(self, symbol: str, qty: int, avg_price: int):
        """포지션 변경 시 호출"""
        # 1초 후 보유 현황 갱신
        QTimer.singleShot(1000, self.update_holdings)

    def show_status_message(self, msg: str):
        """상태 메시지 표시"""
        self.statusBar().showMessage(msg, 5000)

    def toggle_auto_trading(self, checked: bool):
        """자동매매 ON/OFF 토글"""
        if checked:
            self.btn_toggle_auto.setText("자동매매 중지")
            self.auto_trader.start()
        else:
            self.btn_toggle_auto.setText("자동매매 시작")
            self.auto_trader.stop()

    def closeEvent(self, event):
        """윈도우 종료 시 정리"""
        self.auto_trader.stop()
        event.accept() 