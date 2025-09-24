#!/usr/bin/env python3
"""
키움증권 REST API 자동매매 시스템 메인 실행 파일
- PyQt5 GUI 실행
- WebSocket 실시간 데이터 스트리밍
- 자동매매 엔진 연동
"""

import sys
import os

# 현재 스크립트의 디렉토리를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from PyQt5.QtWidgets import QApplication
from gui import MiniHTSWindow
from auth import initialize_auth

def main():
    """메인 함수"""
    print("키움증권 REST API 자동매매 시스템 시작...")
    
    # 인증 토큰 초기화
    print("인증 토큰 발급 중...")
    try:
        initialize_auth()
    except Exception as e:
        print(f"[인증 오류] {e}")
        print("토큰 발급에 실패했지만 GUI는 실행합니다.")
    
    # GUI 실행
    app = QApplication(sys.argv)
    
    # 모니터링 대상 종목 (메이저 종목들)
    target_symbols = [
        "005930",  # 삼성전자
        "000660",  # SK하이닉스
        "035420",  # NAVER
        "373220",  # LG에너지솔루션
        "005380"   # 현대차
    ]
    
    # 메인 윈도우 생성 및 표시
    window = MiniHTSWindow(target_symbols)
    window.show()
    
    print("GUI 실행 완료. 종목 검색 및 실시간 차트를 사용해보세요!")
    print("✨ 새로운 기능:")
    print("  📊 실시간 10분봉 캔들차트")
    print("  📈 RSI 지표 (과매수/과매도 신호)")
    print("  🔍 종목 검색 (코드 또는 이름으로)")
    print("  📋 종목명 표시")
    
    # 이벤트 루프 실행
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 