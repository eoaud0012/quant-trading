# 🚀 빠른 시작 가이드

## 1분 안에 시작하기

### 1. 패키지 설치
```bash
pip install numpy pandas requests websocket-client python-dotenv PyQt5
```

### 2. API 키 설정
`src/config.py` 파일을 열고 본인의 키로 변경:
```python
APP_KEY = "30fa5r73sctbR_ntaqC1JgfsAJ-negNqfQsPm27ZD2U"     # 여기에 본인 키
SECRET_KEY = "0PVRC1RVnceNPum0l-I7xYZYKZ2FjYMV8b1g5F9lzaI"  # 여기에 본인 키
```

### 3. 실행
```bash
python run.py
```

## ⚠️ 실행 전 확인사항

- [ ] 키움증권 REST API 사용 신청 완료
- [ ] API 키 발급 완료
- [ ] 사용할 PC의 IP 주소를 허용 목록에 추가
- [ ] Python 3.8 이상 설치

## 🔧 모의투자로 시작하기

실제 돈으로 테스트하기 전에 모의투자로 시작하세요!

`src/config.py`에서:
```python
# 운영 서버 (실제 거래)
# BASE_URL = "https://api.kiwoom.com"

# 모의투자 서버 (테스트용) - 이 줄의 주석을 해제하세요
BASE_URL = "https://mockapi.kiwoom.com"
```

## 📊 화면 설명

프로그램을 실행하면:
- **좌측**: 차트/호가 영역 (향후 구현 예정)
- **우측 상단**: 보유 종목 현황 테이블
- **우측 하단**: 총 보유현황 및 자동매매 시작/중지 버튼

## 🎯 거래 전략

1. **매수**: RSI 30 이하에서 자동 매수
2. **매도**: 
   - 2% 수익 시 → 50% 매도
   - 3% 수익 시 → 나머지 전량 매도

## ❓ 문제 발생 시

### "토큰 발급 실패" 메시지가 나올 때
1. API 키가 정확한지 확인
2. IP 주소가 허용되었는지 확인
3. 인터넷 연결 확인

### GUI가 나타나지 않을 때
```bash
pip install --upgrade PyQt5
```

더 자세한 내용은 `README.md`를 참고하세요! 