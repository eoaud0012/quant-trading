"""
PyQt5 기반 미니 HTS GUI
- 보유 종목 현황 표시
- 자동매매 ON/OFF 제어
- 실시간 상태 메시지 표시
"""

import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from .api import get_holdings_rest
from .auto_trader import AutoTrader


class MiniHTSWindow(QMainWindow):
    """
    PyQt5 기반 "미니 HTS" GUI – REST API 버전
    - 좌측: 실시간 차트/호가 영역 (placeholder)
    - 우측 상단: 보유 종목 테이블
    - 우측 하단: 총 보유 현황, 자동매매 ON/OFF 토글 버튼
    """

    def __init__(self, symbols: list):
        super().__init__()
        self.symbols = symbols
        self.auto_trader = AutoTrader(symbols)

        self.setWindowTitle("키움증권 자동매매 시스템 (REST API)")
        self.setGeometry(100, 100, 1400, 900)
        
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
        
        # 초기 보유 현황 조회
        self.update_holdings()

    def _init_ui(self):
        """UI 초기화"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # ┌─────────────────────────────────────────┐
        # │ 좌측: 실시간 차트/호가 영역 (placeholder) │
        # └─────────────────────────────────────────┘
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        title_label = QLabel("실시간 차트 / 호가")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        left_layout.addWidget(title_label)
        
        self.chart_placeholder = QLabel("차트 영역\n(WebSocket + pyqtgraph로 구현 예정)")
        self.chart_placeholder.setAlignment(Qt.AlignCenter)
        self.chart_placeholder.setStyleSheet("""
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
            color: #666;
        """)
        self.chart_placeholder.setMinimumHeight(400)
        left_layout.addWidget(self.chart_placeholder)
        
        left_widget.setMinimumWidth(700)

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
        main_layout.addWidget(left_widget, 3)
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
        df = get_holdings_rest()
        
        if df.empty:
            self.holdings_table.setRowCount(0)
            self.total_qty_label.setText("총 보유 주수: 0 주")
            self.total_profit_label.setText("총 평가손익: 0 원")
            return

        row_count = len(df)
        self.holdings_table.setRowCount(row_count)
        total_qty, total_profit = 0, 0

        for idx, row in enumerate(df.itertuples()):
            symbol = str(row.종목코드)
            name = str(row.종목명)
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