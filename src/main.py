"""
키움증권 REST API 자동매매 시스템
메인 실행 파일
"""

import sys
from PyQt5.QtWidgets import QApplication

from .auth import initialize_auth
from .gui import MiniHTSWindow
from .config import DEFAULT_SYMBOLS


def main():
    """
    메인 실행 함수
    """
    # 1. 인증 초기화 (토큰 발급 및 자동 갱신 시작)
    print("키움증권 REST API 자동매매 시스템 시작...")
    print("인증 토큰 발급 중...")
    
    try:
        initialize_auth()
    except Exception as e:
        print(f"[오류] 인증 실패: {str(e)}")
        print("다음 사항을 확인해주세요:")
        print("1. API 키가 올바른지")
        print("2. IP 주소가 허용 목록에 있는지")
        print("3. 인터넷 연결이 정상인지")
        return 1
    
    # 2. PyQt5 앱 시작
    app = QApplication(sys.argv)
    
    # 3. 메인 윈도우 생성 및 표시
    window = MiniHTSWindow(DEFAULT_SYMBOLS)
    window.show()
    
    # 4. 이벤트 루프 실행
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main()) 