"""
키움증권 REST API 설정 및 전략 파라미터
"""

# API 인증 정보
APP_KEY = "30fa5r73sctbR_ntaqC1JgfsAJ-negNqfQsPm27ZD2U"
SECRET_KEY = "0PVRC1RVnceNPum0l-I7xYZYKZ2FjYMV8b1g5F9lzaI"

# API 엔드포인트 URL
# 운영 서버 사용 시
BASE_URL = "https://api.kiwoom.com"
TOKEN_URL = f"{BASE_URL}/oauth2/token"
WS_URL = "wss://api.kiwoom.com/v1/streaming"

# 모의투자 서버 사용 시 (필요시 주석 해제)
# BASE_URL = "https://mockapi.kiwoom.com"
# TOKEN_URL = f"{BASE_URL}/oauth2/token"
# WS_URL = "wss://mockapi.kiwoom.com/v1/streaming"

# 전략 파라미터
OVERSOLD_RSI_THRESHOLD = 30  # RSI 과매도 기준
TARGET_PROFIT_FIRST = 0.02   # 1차 목표 수익률 (2%)
TARGET_PROFIT_SECOND = 0.03  # 2차 목표 수익률 (3%)
MAX_ORDERBOOK_LEVELS = 5     # 호가 레벨 수

# API 호출 딜레이 (초)
TR_SLEEP_SHORT = 0.1

# 거래 대상 종목 (예시)
DEFAULT_SYMBOLS = ["091990", "096770", "069500", "003490", "005380"] 