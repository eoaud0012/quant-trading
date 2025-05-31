# 키움증권 REST API 자동매매 시스템

키움증권 REST API를 활용한 파이썬 기반 자동매매 시스템입니다.

## 주요 기능

- **자동 토큰 관리**: Access Token 자동 발급 및 갱신
- **실시간 데이터 수신**: WebSocket을 통한 실시간 체결가/호가 모니터링
- **기술적 분석**: RSI, 이동평균 등 지표 기반 매매 전략
- **자동매매**: 과매도 시 매수, 목표 수익률 달성 시 매도
- **GUI 인터페이스**: PyQt5 기반 실시간 모니터링 화면

## 전략 개요

1. **매수 조건**:
   - 일봉 기준 단기 상승 추세 (5일선 > 20일선)
   - 10분봉 RSI 30 이하 (과매도)
   - 호가 5레벨에 분산 매수

2. **매도 조건**:
   - 1차 매도: 수익률 2% 달성 시 보유량의 50% 매도
   - 2차 매도: 수익률 3% 달성 시 나머지 전량 매도

## 설치 방법

### 1. 필수 패키지 설치

```bash
pip install -r requirements.txt
```

### 2. API 설정

`src/config.py` 파일에서 본인의 API 키 설정:

```python
APP_KEY = "your_app_key"
SECRET_KEY = "your_secret_key"
```

### 3. IP 주소 허용

키움증권 개발자 사이트에서 사용할 PC의 IP 주소를 허용 목록에 추가해야 합니다.

## 실행 방법

```bash
python run.py
```

## 프로젝트 구조

```
quant-trading/
├── src/
│   ├── __init__.py
│   ├── config.py          # 설정 파일
│   ├── auth.py            # 인증 관리
│   ├── api.py             # REST API 호출 함수
│   ├── websocket_streamer.py  # WebSocket 실시간 데이터
│   ├── indicators.py      # 기술적 지표 계산
│   ├── auto_trader.py     # 자동매매 엔진
│   ├── gui.py             # PyQt5 GUI
│   └── main.py            # 메인 실행
├── run.py                 # 실행 스크립트
├── requirements.txt       # 의존성 패키지
└── README.md             # 이 파일
```

## 주의사항

1. **실제 거래 주의**: 이 시스템은 실제 자금으로 거래를 수행합니다. 충분한 테스트 후 사용하세요.
2. **모의투자 권장**: 먼저 모의투자 서버에서 테스트하려면 `src/config.py`에서 URL을 변경하세요:
   ```python
   BASE_URL = "https://mockapi.kiwoom.com"
   ```
3. **리스크 관리**: 적절한 자금 관리와 손절 전략을 수립하세요.

## 문제 해결

### 토큰 발급 실패
- API 키가 올바른지 확인
- IP 주소가 허용 목록에 있는지 확인
- 인터넷 연결 상태 확인

### WebSocket 연결 실패
- 토큰이 정상적으로 발급되었는지 확인
- 방화벽 설정 확인

## 라이선스

MIT License 