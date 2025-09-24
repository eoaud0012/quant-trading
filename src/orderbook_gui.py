#!/usr/bin/env python3
"""
키움증권 호가창 GUI - 간소화 버전
"""

import sys
import random
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QLineEdit, QFrame, QGroupBox, QSpinBox,
    QMessageBox, QGridLayout, QTabWidget
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor

from api import get_market_data_rest, place_market_order_rest, place_limit_order_rest, get_holdings_rest
from auth import initialize_auth
from stock_master import get_all_stock_dict, search_stocks_comprehensive

# 전체 종목 딕셔너리
ALL_STOCK_DICT = None

def get_stock_name(code):
    """종목코드로 종목명 조회"""
    global ALL_STOCK_DICT
    if ALL_STOCK_DICT is None:
        ALL_STOCK_DICT = get_all_stock_dict()
    return ALL_STOCK_DICT.get(code, code)

def search_stocks(query):
    """종목 검색"""
    global ALL_STOCK_DICT
    if ALL_STOCK_DICT is None:
        ALL_STOCK_DICT = get_all_stock_dict()
    return search_stocks_comprehensive(query, ALL_STOCK_DICT)


class HoldingsWidget(QWidget):
    """잔고 현황 위젯"""
    
    def __init__(self):
        super().__init__()
        self._init_ui()
        self._init_timer()
        self.refresh_holdings()
    
    def _init_ui(self):
        """잔고 현황 UI 초기화"""
        layout = QVBoxLayout(self)
        
        # 제목
        title_label = QLabel("💰 내 잔고 현황")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 잔고 테이블
        self.holdings_table = QTableWidget(0, 6)
        self.holdings_table.setHorizontalHeaderLabels([
            "종목코드", "종목명", "보유수량", "매입단가", "현재가", "평가손익"
        ])
        self.holdings_table.verticalHeader().setVisible(False)
        self.holdings_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.holdings_table.setAlternatingRowColors(True)
        
        # 컬럼 너비 자동 조정
        header = self.holdings_table.horizontalHeader()
        header.setStretchLastSection(True)
        for i in range(5):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        layout.addWidget(self.holdings_table)
        
        # 요약 정보
        self.summary_label = QLabel("총 평가금액: 계산 중...")
        self.summary_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.summary_label.setAlignment(Qt.AlignCenter)
        self.summary_label.setStyleSheet("background-color: #f8f9fa; padding: 10px; border: 1px solid #dee2e6; border-radius: 5px;")
        layout.addWidget(self.summary_label)
        
        # 새로고침 버튼
        refresh_btn = QPushButton("🔄 잔고 새로고침")
        refresh_btn.clicked.connect(self.refresh_holdings)
        layout.addWidget(refresh_btn)
    
    def _init_timer(self):
        """잔고 자동 갱신 타이머 (10초마다)"""
        self.holdings_timer = QTimer()
        self.holdings_timer.timeout.connect(self.refresh_holdings)
        self.holdings_timer.start(10000)  # 10초마다 갱신
    
    def refresh_holdings(self):
        """잔고 현황 새로고침"""
        try:
            print("[잔고 조회] 실제 API 호출 중...")
            holdings_df = get_holdings_rest()
            
            # 테이블 초기화
            self.holdings_table.setRowCount(0)
            
            if holdings_df.empty:
                print("[잔고 현황] API에서 데이터가 없습니다 - 보유 종목이 없거나 API 오류")
                # 빈 상태 표시
                self.holdings_table.setRowCount(1)
                empty_item = QTableWidgetItem("보유 종목이 없습니다")
                empty_item.setTextAlignment(Qt.AlignCenter)
                empty_item.setFont(QFont("Arial", 12))
                empty_item.setForeground(QColor(128, 128, 128))
                self.holdings_table.setItem(0, 1, empty_item)
                
                # 다른 셀들 비우기
                for col in [0, 2, 3, 4, 5]:
                    self.holdings_table.setItem(0, col, QTableWidgetItem(""))
                
                self.summary_label.setText(
                    f"총 평가금액: 0원 | "
                    f"<span style='color: gray; font-weight: bold;'>총 손익: 0원 (0.00%)</span> | "
                    f"갱신: {datetime.now().strftime('%H:%M:%S')}"
                )
                
            else:
                # 실제 API 데이터 표시
                print(f"[잔고 현황] 실제 API 데이터 표시 - 총 {len(holdings_df)}개 종목")
                self.holdings_table.setRowCount(len(holdings_df))
                
                total_value = 0
                total_profit = 0
                
                for row, (idx, holding) in enumerate(holdings_df.iterrows()):
                    self.holdings_table.setItem(row, 0, QTableWidgetItem(str(holding['종목코드'])))
                    self.holdings_table.setItem(row, 1, QTableWidgetItem(str(holding['종목명'])))
                    self.holdings_table.setItem(row, 2, QTableWidgetItem(str(holding['보유수량'])))
                    self.holdings_table.setItem(row, 3, QTableWidgetItem(str(holding['매입단가'])))
                    self.holdings_table.setItem(row, 4, QTableWidgetItem(str(holding['현재가'])))
                    
                    profit_item = QTableWidgetItem(str(holding['평가손익']))
                    try:
                        profit_val = float(str(holding['평가손익']).replace(',', '').replace('+', ''))
                        if profit_val >= 0:
                            profit_item.setForeground(QColor(220, 20, 60))  # 빨간색 (수익)
                        else:
                            profit_item.setForeground(QColor(20, 90, 200))  # 파란색 (손실)
                        total_profit += profit_val
                        
                        # 현재 평가금액 계산
                        qty = int(str(holding['보유수량']).replace(',', ''))
                        curr_price = float(str(holding['현재가']).replace(',', ''))
                        total_value += qty * curr_price
                        
                    except (ValueError, TypeError):
                        profit_item.setForeground(QColor(128, 128, 128))
                    
                    profit_item.setFont(QFont("Arial", 10, QFont.Bold))
                    self.holdings_table.setItem(row, 5, profit_item)
                
                # 요약 정보 업데이트
                if total_value > 0:
                    profit_rate = (total_profit / (total_value - total_profit)) * 100 if total_value > total_profit else 0
                    color = "red" if total_profit >= 0 else "blue"
                    sign = "+" if total_profit >= 0 else ""
                    
                    self.summary_label.setText(
                        f"총 평가금액: {total_value:,.0f}원 | "
                        f"<span style='color: {color}; font-weight: bold;'>"
                        f"총 손익: {sign}{total_profit:,.0f}원 ({profit_rate:+.2f}%)"
                        f"</span> | "
                        f"갱신: {datetime.now().strftime('%H:%M:%S')}"
                    )
                else:
                    self.summary_label.setText(f"갱신: {datetime.now().strftime('%H:%M:%S')} - 데이터 처리 중...")
                
        except Exception as e:
            print(f"[잔고 조회 오류] {str(e)}")
            self.summary_label.setText(f"⚠️ 잔고 조회 오류: {str(e)[:50]}...")
            
            # 오류 상태 표시
            self.holdings_table.setRowCount(1)
            error_item = QTableWidgetItem(f"오류: {str(e)[:30]}...")
            error_item.setTextAlignment(Qt.AlignCenter)
            error_item.setForeground(QColor(255, 0, 0))
            self.holdings_table.setItem(0, 1, error_item)
            
            for col in [0, 2, 3, 4, 5]:
                self.holdings_table.setItem(0, col, QTableWidgetItem(""))


class OrderBookWidget(QWidget):
    """호가창 위젯"""
    
    def __init__(self, symbol: str, exchange: str = "KRX"):
        super().__init__()
        self.symbol = symbol
        self.exchange = exchange
        self.stock_name = get_stock_name(symbol)
        
        # 호가 데이터
        self.ask_orders = {}  # 매도 호가 (빨간색)
        self.bid_orders = {}  # 매수 호가 (파란색)
        self.current_price = 50000
        
        self._init_ui()
        self._init_timer()
        self.generate_sample_orderbook()
    
    def _init_ui(self):
        """호가창 UI 초기화"""
        layout = QVBoxLayout(self)
        
        # 종목 정보
        self.stock_title = QLabel(f"{self.symbol} - {self.stock_name}")
        self.stock_title.setFont(QFont("Arial", 16, QFont.Bold))
        self.stock_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.stock_title)
        
        # 현재가 정보
        self.price_info = QLabel("현재가: 로딩 중...")
        self.price_info.setFont(QFont("Arial", 14, QFont.Bold))
        self.price_info.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.price_info)
        
        # 메인 레이아웃 (호가창 + 주문)
        main_layout = QHBoxLayout()
        
        # 호가창 테이블
        self.orderbook_table = QTableWidget(21, 4)
        self.orderbook_table.setHorizontalHeaderLabels(["매도잔량", "매도호가", "매수호가", "매수잔량"])
        self.orderbook_table.verticalHeader().setVisible(False)
        self.orderbook_table.setSelectionMode(QTableWidget.SingleSelection)  # 단일 선택 가능
        self.orderbook_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # 클릭 이벤트 연결
        self.orderbook_table.cellClicked.connect(self.on_price_clicked)
        
        # 행 높이 설정
        for row in range(21):
            self.orderbook_table.setRowHeight(row, 30)
        
        main_layout.addWidget(self.orderbook_table, 2)  # 호가창이 더 넓게
        
        # 주문 패널
        order_panel = self._create_order_panel()
        main_layout.addWidget(order_panel, 1)
        
        layout.addLayout(main_layout)
        
        # 클릭 가이드
        guide_label = QLabel("🎯 클릭 주문: 매도호가(빨간색) 클릭=매수주문 | 매수호가(파란색) 클릭=매도주문")
        guide_label.setFont(QFont("Arial", 10))
        guide_label.setStyleSheet("color: #666; background-color: #e8f4f8; padding: 8px; border-radius: 5px; border-left: 4px solid #17a2b8;")
        layout.addWidget(guide_label)
        
        # 새로고침 버튼
        refresh_btn = QPushButton("수동 새로고침")
        refresh_btn.clicked.connect(self.refresh_orderbook)
        layout.addWidget(refresh_btn)
    
    def on_price_clicked(self, row, col):
        """호가 가격 클릭 시 처리"""
        try:
            # 가격 셀이 아니면 무시
            if col not in [1, 2]:  # 매도호가, 매수호가 컬럼만
                return
            
            item = self.orderbook_table.item(row, col)
            if not item or not item.text().strip():
                return
            
            # 가격 추출 (콤마 제거)
            price_text = item.text().replace(',', '')
            if not price_text.isdigit():
                return
            
            price = int(price_text)
            
            # 직관적인 로직: 매도호가 클릭 = 매도 주문, 매수호가 클릭 = 매수 주문
            if col == 1 and row < 10:  # 매도호가 영역 (빨간색)
                side = "SELL"
                order_type = "매도"
                color = "🔴"
                message = f"매도호가 {price:,}원에 매도주문"
            elif col == 2 and row > 10:  # 매수호가 영역 (파란색)
                side = "BUY"
                order_type = "매수"
                color = "🔵"
                message = f"매수호가 {price:,}원에 매수주문"
            else:
                return
            
            # 지정가 스핀박스에 클릭한 가격 설정
            self.price_spinbox.setValue(price)
            
            # 수량 가져오기
            qty = self.qty_spinbox.value()
            
            # 즉시 주문 실행 (확인창 없음)
            print(f"{color} 클릭 주문 즉시 실행: {message}, 수량: {qty}주")
            self.execute_click_order(side, price, qty)
                
        except Exception as e:
            print(f"[클릭 주문 오류] {str(e)}")
            QMessageBox.warning(self, "오류", f"클릭 주문 처리 중 오류가 발생했습니다:\n{str(e)}")
    
    def execute_click_order(self, side, price, qty):
        """클릭 주문 실행"""
        try:
            result = place_limit_order_rest(self.symbol, side, qty, price, self.exchange)
            order_desc = f"클릭 지정가 {side}"
            
            return_code = result.get("return_code", -1)
            return_msg = result.get("return_msg", "알 수 없는 오류")
            ord_no = result.get("ord_no", "")
            
            if return_code == 0:
                success_msg = f"🎯 클릭 주문 성공!\n{order_desc} @{price:,}원\n수량: {qty}주\n주문번호: {ord_no}"
                self.order_result.setText(success_msg)
                self.order_result.setStyleSheet("background-color: #d4edda; color: #155724; padding: 5px; border: 1px solid #c3e6cb;")
                print(f"✅ 주문 성공: {order_desc} @{price:,}원, 수량: {qty}주")
            else:
                error_msg = f"❌ 클릭 주문 실패!\n{order_desc} @{price:,}원\n수량: {qty}주\n오류: {return_msg}"
                self.order_result.setText(error_msg)
                self.order_result.setStyleSheet("background-color: #f8d7da; color: #721c24; padding: 5px; border: 1px solid #f5c6cb;")
                print(f"❌ 주문 실패: {order_desc} @{price:,}원, 오류: {return_msg}")
            
            print(f"[클릭 주문 결과] {order_desc}, price={price}, qty={qty}, return_code={return_code}, msg={return_msg}")
            
        except Exception as e:
            error_msg = f"❌ 클릭 주문 오류!\n{str(e)}"
            self.order_result.setText(error_msg)
            self.order_result.setStyleSheet("background-color: #f8d7da; color: #721c24; padding: 5px; border: 1px solid #f5c6cb;")
            print(f"[클릭 주문 오류] {str(e)}")
    
    def _create_order_panel(self):
        """주문 패널 생성"""
        order_group = QGroupBox("주문하기")
        order_group.setFont(QFont("Arial", 12, QFont.Bold))
        layout = QVBoxLayout(order_group)
        
        # 거래소 선택
        exchange_layout = QHBoxLayout()
        exchange_layout.addWidget(QLabel("거래소:"))
        self.exchange_combo = QComboBox()
        self.exchange_combo.addItems(["KRX", "NXT", "SOR"])
        self.exchange_combo.setCurrentText(self.exchange)
        self.exchange_combo.currentTextChanged.connect(self.on_exchange_changed)
        exchange_layout.addWidget(self.exchange_combo)
        layout.addLayout(exchange_layout)
        
        # 주문 수량
        qty_layout = QHBoxLayout()
        qty_layout.addWidget(QLabel("수량:"))
        self.qty_spinbox = QSpinBox()
        self.qty_spinbox.setMinimum(1)
        self.qty_spinbox.setMaximum(999999)
        self.qty_spinbox.setValue(10)
        qty_layout.addWidget(self.qty_spinbox)
        layout.addLayout(qty_layout)
        
        # 지정가 입력
        price_layout = QHBoxLayout()
        price_layout.addWidget(QLabel("지정가:"))
        self.price_spinbox = QSpinBox()
        self.price_spinbox.setMinimum(1)
        self.price_spinbox.setMaximum(9999999)
        self.price_spinbox.setValue(self.current_price)
        price_layout.addWidget(self.price_spinbox)
        layout.addLayout(price_layout)
        
        # 주문 버튼들
        buttons_layout = QGridLayout()
        
        # 시장가 주문
        self.market_buy_btn = QPushButton("시장가 매수")
        self.market_buy_btn.setStyleSheet("background-color: #ff4444; color: white; font-weight: bold;")
        self.market_buy_btn.clicked.connect(lambda: self.place_order("BUY", "MARKET"))
        buttons_layout.addWidget(self.market_buy_btn, 0, 0)
        
        self.market_sell_btn = QPushButton("시장가 매도")
        self.market_sell_btn.setStyleSheet("background-color: #4444ff; color: white; font-weight: bold;")
        self.market_sell_btn.clicked.connect(lambda: self.place_order("SELL", "MARKET"))
        buttons_layout.addWidget(self.market_sell_btn, 0, 1)
        
        # 지정가 주문
        self.limit_buy_btn = QPushButton("지정가 매수")
        self.limit_buy_btn.setStyleSheet("background-color: #ff8888; color: white; font-weight: bold;")
        self.limit_buy_btn.clicked.connect(lambda: self.place_order("BUY", "LIMIT"))
        buttons_layout.addWidget(self.limit_buy_btn, 1, 0)
        
        self.limit_sell_btn = QPushButton("지정가 매도")
        self.limit_sell_btn.setStyleSheet("background-color: #8888ff; color: white; font-weight: bold;")
        self.limit_sell_btn.clicked.connect(lambda: self.place_order("SELL", "LIMIT"))
        buttons_layout.addWidget(self.limit_sell_btn, 1, 1)
        
        layout.addLayout(buttons_layout)
        
        # 주문 결과 표시
        self.order_result = QLabel("주문 대기 중...")
        self.order_result.setWordWrap(True)
        self.order_result.setStyleSheet("background-color: #f0f0f0; padding: 5px; border: 1px solid #ccc;")
        layout.addWidget(self.order_result)
        
        return order_group
    
    def on_exchange_changed(self, exchange):
        """거래소 변경 시"""
        self.exchange = exchange
        print(f"[거래소 변경] {self.symbol} -> {exchange}")
    
    def place_order(self, side, order_type):
        """주문 실행"""
        qty = self.qty_spinbox.value()
        price = self.price_spinbox.value()
        
        try:
            if order_type == "MARKET":
                # 시장가 주문
                result = place_market_order_rest(self.symbol, side, qty, self.exchange)
                order_desc = f"시장가 {side}"
            else:
                # 지정가 주문
                result = place_limit_order_rest(self.symbol, side, qty, price, self.exchange)
                order_desc = f"지정가 {side} @{price:,}원"
            
            return_code = result.get("return_code", -1)
            return_msg = result.get("return_msg", "알 수 없는 오류")
            ord_no = result.get("ord_no", "")
            
            if return_code == 0:
                self.order_result.setText(f"✅ 주문 성공!\n{order_desc}\n수량: {qty}주\n주문번호: {ord_no}")
                self.order_result.setStyleSheet("background-color: #d4edda; color: #155724; padding: 5px; border: 1px solid #c3e6cb;")
            else:
                self.order_result.setText(f"❌ 주문 실패!\n{order_desc}\n수량: {qty}주\n오류: {return_msg}")
                self.order_result.setStyleSheet("background-color: #f8d7da; color: #721c24; padding: 5px; border: 1px solid #f5c6cb;")
            
            print(f"[주문 결과] {order_desc}, qty={qty}, return_code={return_code}, msg={return_msg}")
            
        except Exception as e:
            error_msg = f"❌ 주문 오류!\n{str(e)}"
            self.order_result.setText(error_msg)
            self.order_result.setStyleSheet("background-color: #f8d7da; color: #721c24; padding: 5px; border: 1px solid #f5c6cb;")
            print(f"[주문 오류] {str(e)}")
    
    def _init_timer(self):
        """타이머 초기화"""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.update_orderbook)
        self.refresh_timer.start(1000)  # 1초마다 갱신 (최대한 빠르게)
    
    def generate_sample_orderbook(self):
        """샘플 호가 데이터 생성"""
        # 실제 현재가가 있으면 그것을 사용, 없으면 하드코딩된 가격 사용
        if not hasattr(self, 'current_price') or self.current_price <= 1000:
            stock_prices = {
                "005930": 58000,    # 삼성전자
                "000660": 120000,   # SK하이닉스  
                "035420": 190000,   # NAVER
                "373220": 400000,   # LG에너지솔루션
                "005380": 170000,   # 현대차
                "272210": 51450,    # 한화시스템
            }
            self.current_price = stock_prices.get(self.symbol, 50000)
            print(f"[호가 생성] {self.symbol} 하드코딩 가격 사용: {self.current_price:,}원")
        else:
            print(f"[호가 생성] {self.symbol} 실제 현재가 사용: {self.current_price:,}원")
        
        # 호가 단위 계산
        if self.current_price < 2000:
            tick_size = 1
        elif self.current_price < 5000:
            tick_size = 5
        elif self.current_price < 20000:
            tick_size = 10
        elif self.current_price < 50000:
            tick_size = 50
        elif self.current_price < 200000:
            tick_size = 100
        else:
            tick_size = 250
        
        # 매도 호가 10개 생성
        self.ask_orders = {}
        for i in range(1, 11):
            price = self.current_price + (tick_size * i)
            quantity = random.randint(100, 5000)
            self.ask_orders[price] = quantity
        
        # 매수 호가 10개 생성
        self.bid_orders = {}
        for i in range(1, 11):
            price = self.current_price - (tick_size * i)
            if price > 0:
                quantity = random.randint(100, 5000)
                self.bid_orders[price] = quantity
        
        # 지정가 스핀박스 업데이트
        self.price_spinbox.setValue(self.current_price)
        
        self.update_orderbook_display()
    
    def update_orderbook_display(self):
        """호가창 테이블 업데이트"""
        ask_prices = sorted(self.ask_orders.keys(), reverse=True)
        bid_prices = sorted(self.bid_orders.keys(), reverse=True)
        
        for row in range(21):
            if row < 10:
                # 매도 호가 영역 (빨간색)
                if row < len(ask_prices):
                    price = ask_prices[row]
                    quantity = self.ask_orders[price]
                    
                    qty_item = QTableWidgetItem(f"{quantity:,}")
                    qty_item.setTextAlignment(Qt.AlignCenter)
                    qty_item.setBackground(QColor(255, 240, 240))  # 연한 빨간색 배경
                    self.orderbook_table.setItem(row, 0, qty_item)
                    
                    price_item = QTableWidgetItem(f"{price:,}")
                    price_item.setTextAlignment(Qt.AlignCenter)
                    price_item.setForeground(QColor(220, 20, 60))  # 빨간색 텍스트
                    price_item.setFont(QFont("Arial", 10, QFont.Bold))
                    price_item.setBackground(QColor(255, 240, 240))  # 연한 빨간색 배경
                    self.orderbook_table.setItem(row, 1, price_item)
                    
                    self.orderbook_table.setItem(row, 2, QTableWidgetItem(""))
                    self.orderbook_table.setItem(row, 3, QTableWidgetItem(""))
                else:
                    # 빈 셀 처리
                    for col in range(4):
                        self.orderbook_table.setItem(row, col, QTableWidgetItem(""))
                
            elif row == 10:
                # 현재가 영역 (노란색)
                self.orderbook_table.setItem(row, 0, QTableWidgetItem(""))
                
                current_item = QTableWidgetItem(f"{self.current_price:,}")
                current_item.setTextAlignment(Qt.AlignCenter)
                current_item.setFont(QFont("Arial", 12, QFont.Bold))
                current_item.setBackground(QColor(255, 255, 0))  # 노란색 배경
                current_item.setForeground(QColor(0, 0, 0))  # 검은색 텍스트
                self.orderbook_table.setItem(row, 1, current_item)
                
                current_item2 = QTableWidgetItem(f"{self.current_price:,}")
                current_item2.setTextAlignment(Qt.AlignCenter)
                current_item2.setFont(QFont("Arial", 12, QFont.Bold))
                current_item2.setBackground(QColor(255, 255, 0))  # 노란색 배경
                current_item2.setForeground(QColor(0, 0, 0))  # 검은색 텍스트
                self.orderbook_table.setItem(row, 2, current_item2)
                
                self.orderbook_table.setItem(row, 3, QTableWidgetItem(""))
                
            else:
                # 매수 호가 영역 (파란색)
                bid_index = row - 11
                if bid_index < len(bid_prices):
                    price = bid_prices[bid_index]
                    quantity = self.bid_orders[price]
                    
                    self.orderbook_table.setItem(row, 0, QTableWidgetItem(""))
                    self.orderbook_table.setItem(row, 1, QTableWidgetItem(""))
                    
                    price_item = QTableWidgetItem(f"{price:,}")
                    price_item.setTextAlignment(Qt.AlignCenter)
                    price_item.setForeground(QColor(20, 90, 200))  # 파란색 텍스트
                    price_item.setFont(QFont("Arial", 10, QFont.Bold))
                    price_item.setBackground(QColor(240, 240, 255))  # 연한 파란색 배경
                    self.orderbook_table.setItem(row, 2, price_item)
                    
                    qty_item = QTableWidgetItem(f"{quantity:,}")
                    qty_item.setTextAlignment(Qt.AlignCenter)
                    qty_item.setBackground(QColor(240, 240, 255))  # 연한 파란색 배경
                    self.orderbook_table.setItem(row, 3, qty_item)
                else:
                    # 빈 셀 처리
                    for col in range(4):
                        self.orderbook_table.setItem(row, col, QTableWidgetItem(""))
        
        # 현재가 정보 업데이트
        ask_1 = min(self.ask_orders.keys()) if self.ask_orders else self.current_price  # 최우선 매도호가
        bid_1 = max(self.bid_orders.keys()) if self.bid_orders else self.current_price  # 최우선 매수호가
        spread = ask_1 - bid_1
        
        info_text = f"현재가: {self.current_price:,}원 | 매도1호가: {ask_1:,}원 | 매수1호가: {bid_1:,}원 | 스프레드: {spread:,}원"
        self.price_info.setText(info_text)
    
    def update_orderbook(self):
        """호가 데이터 업데이트"""
        try:
            market_data = get_market_data_rest(self.symbol)
            if market_data and 'stck_prpr' in market_data:
                current_price_str = market_data['stck_prpr']
                if current_price_str and current_price_str != "0":
                    new_price = int(current_price_str.replace('+', '').replace('-', ''))
                    self.current_price = new_price
                    self.generate_sample_orderbook()
                    print(f"[호가창 API 업데이트] {self.symbol}@{self.exchange}, 현재가={new_price}")
                    return
        except Exception as e:
            print(f"[호가창 API 오류] {str(e)}")
        
        # API 실패 시 시뮬레이션
        change_rate = random.uniform(-0.001, 0.001)
        self.current_price = max(1000, int(self.current_price * (1 + change_rate)))
        self.generate_sample_orderbook()
    
    def refresh_orderbook(self):
        """수동 새로고침"""
        self.generate_sample_orderbook()
        self.order_result.setText("수동 새로고침 완료!")
        self.order_result.setStyleSheet("background-color: #d1ecf1; color: #0c5460; padding: 5px; border: 1px solid #bee5eb;")
    
    def change_symbol(self, new_symbol: str):
        """종목 변경"""
        self.symbol = new_symbol
        self.stock_name = get_stock_name(new_symbol)
        self.stock_title.setText(f"{self.symbol} - {self.stock_name}")
        
        # 실제 API에서 현재가 조회
        try:
            print(f"[종목 변경] {new_symbol} ({self.stock_name}) - 실제 현재가 조회 중...")
            market_data = get_market_data_rest(new_symbol)
            if market_data and 'stck_prpr' in market_data:
                current_price_str = market_data['stck_prpr']
                if current_price_str and current_price_str != "0":
                    self.current_price = int(current_price_str.replace('+', '').replace('-', ''))
                    print(f"[종목 변경] {new_symbol} 실제 현재가: {self.current_price:,}원")
                else:
                    print(f"[종목 변경] {new_symbol} API 응답에 가격 정보 없음")
                    # 기본값 사용
                    self.current_price = 50000
            else:
                print(f"[종목 변경] {new_symbol} API 조회 실패")
                # 기본값 사용
                self.current_price = 50000
        except Exception as e:
            print(f"[종목 변경 오류] {new_symbol}: {str(e)}")
            # 기본값 사용
            self.current_price = 50000
        
        # 지정가 스핀박스 업데이트
        self.price_spinbox.setValue(self.current_price)
        
        # 호가 데이터 생성
        self.generate_sample_orderbook()


class OrderBookWindow(QMainWindow):
    """호가창 메인 윈도우"""
    
    def __init__(self, symbols: list):
        super().__init__()
        self.symbols = symbols
        
        # 🔑 인증 초기화 (토큰 문제 해결)
        print("🔑 키움증권 API 인증 초기화 중...")
        try:
            initialize_auth()
            print("✅ API 인증 성공!")
        except Exception as e:
            print(f"❌ API 인증 실패: {str(e)}")
            QMessageBox.warning(None, "인증 오류", f"키움증권 API 인증에 실패했습니다:\n{str(e)}\n\n계속 진행하지만 주문 기능이 제한될 수 있습니다.")
        
        self.setWindowTitle("키움증권 호가창 시스템")
        self.setGeometry(100, 100, 1200, 800)
        
        self._init_ui()
    
    def _init_ui(self):
        """UI 초기화"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        
        # 왼쪽: 호가창 위젯
        self.orderbook_widget = OrderBookWidget(self.symbols[0], "KRX")
        main_layout.addWidget(self.orderbook_widget, 3)  # 3의 비율
        
        # 오른쪽: 잔고 현황 위젯
        self.holdings_widget = HoldingsWidget()
        main_layout.addWidget(self.holdings_widget, 2)  # 2의 비율
        
        self.statusBar().showMessage("호가창 준비 완료")


def main():
    """호가창 GUI 실행"""
    app = QApplication(sys.argv)
    
    target_symbols = [
        "005930",  # 삼성전자
    ]
    
    window = OrderBookWindow(target_symbols)
    window.show()
    
    print("🚀 키움증권 호가창 GUI 실행 완료!")
    print("✨ 기능:")
    print("  📊 호가창 (주문 포함)")  
    print("  💰 잔고 현황")
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main() 