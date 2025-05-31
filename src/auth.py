"""
키움증권 REST API 인증 관리
- Access Token 발급
- 자동 갱신
"""

import requests
import threading
import datetime
import time
from typing import Optional
from .config import APP_KEY, SECRET_KEY, TOKEN_URL

# 전역 변수: 토큰 정보
access_token: str = ""
token_expiry: Optional[datetime.datetime] = None
LOCK = threading.Lock()


def fetch_access_token() -> None:
    """
    app_key와 secret_key를 이용해 새로운 Access Token을 발급받고,
    전역 변수 access_token, token_expiry를 업데이트한다.
    """
    global access_token, token_expiry

    headers = {
        "Content-Type": "application/json;charset=UTF-8"
    }
    body = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "secretkey": SECRET_KEY
    }
    
    try:
        resp = requests.post(TOKEN_URL, headers=headers, json=body)
        if resp.status_code != 200:
            raise RuntimeError(f"[토큰발급 실패] status_code={resp.status_code}, body={resp.text}")

        data = resp.json()
        # 응답 예: {"token_type":"Bearer","token":"eyJ....","expires_dt":"2025-06-10T12:34:56"}
        with LOCK:
            access_token = data.get("token")
            # expires_dt는 ISO 8601 형식(예: "2025-06-10T12:34:56")으로 옴
            expires_str = data.get("expires_dt")
            # datetime.fromisoformat은 "YYYY-MM-DDTHH:MM:SS" 형식을 파싱
            token_expiry = datetime.datetime.fromisoformat(expires_str)

        print(f"[토큰발급 성공] Access Token 갱신 완료, 만료 시각: {token_expiry.isoformat()}")
        
    except Exception as e:
        print(f"[토큰발급 오류] {str(e)}")
        raise


def token_auto_refresher():
    """
    별도 쓰레드로 동작하며, 토큰 만료 1분 전부터 주기적으로 갱신을 시도한다.
    """
    while True:
        try:
            with LOCK:
                if token_expiry:
                    # 만료 60초 전부터 갱신 시도
                    now = datetime.datetime.now()
                    # KST 시간으로 가정 (필요시 timezone 조정 필요)
                    time_to_expiry = (token_expiry - now).total_seconds()
                else:
                    time_to_expiry = None

            if time_to_expiry is None:
                # 첫 토큰 미발급 상태: 즉시 발급 시도
                try:
                    fetch_access_token()
                except Exception as e:
                    print(f"[토큰발급 예외] {e}, 10초 후 재시도")
                    time.sleep(10)
                continue

            # 토큰 만료 60초 전까지 슬립
            if time_to_expiry > 60:
                # 예: 만료 전까지 token_expiry - 60초 만큼 sleep
                sleep_duration = time_to_expiry - 60
                # 너무 길면 최대 1시간 단위로 쪼개서 대기 (안정성)
                if sleep_duration > 3600:
                    time.sleep(3600)
                else:
                    time.sleep(sleep_duration)
                continue

            # 만료 60초 이내 시 -> 갱신 시도
            try:
                fetch_access_token()
            except Exception as e:
                print(f"[토큰갱신 예외] {e}, 10초 후 다시 시도")
                time.sleep(10)
                
        except Exception as e:
            print(f"[토큰 갱신 스레드 오류] {str(e)}")
            time.sleep(10)


def get_headers() -> dict:
    """
    REST API 호출 시 공통 헤더: Authorization, Content-Type 등을 반환
    """
    with LOCK:
        token = access_token  # 최신 토큰 사용
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json;charset=UTF-8"
    }


def initialize_auth():
    """
    인증 초기화: 토큰 발급 및 자동 갱신 스레드 시작
    """
    # 프로그램 실행 시, 처음 한 번 토큰 발급
    fetch_access_token()
    
    # 토큰 갱신용 백그라운드 스레드 시작 (daemon=True로 설정하여 메인 종료 시 자동 종료)
    threading.Thread(target=token_auto_refresher, daemon=True).start()
    print("[인증 초기화 완료] 토큰 자동 갱신 스레드 시작") 