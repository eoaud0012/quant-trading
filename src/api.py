"""
키움증권 REST API 호출 함수 모음
- 시세 조회 (캔들, 호가)
- 계좌 조회 (잔고)
- 주문 (시장가, 지정가, 취소)
"""

import requests
import pandas as pd
from typing import List, Tuple, Dict
from config import BASE_URL
from auth import get_headers


# ─────────────────────────────────────────────────────────────────────────────
# 시세 조회 API
# ─────────────────────────────────────────────────────────────────────────────

def get_market_data_rest(symbol: str) -> Dict:
    """
    현재가 조회 (ka10004: 주식호가요청을 활용)
    :param symbol: 종목코드 (예: "005930")
    :return: 현재가 정보 딕셔너리 {"stck_prpr": "현재가", ...}
    """
    url = f"{BASE_URL}/api/dostk/mrkcond"
    
    headers = get_headers()
    headers.update({
        'api-id': 'ka10004',  # TR명: 주식호가요청
        'cont-yn': 'N',       # 연속조회여부
        'next-key': ''        # 연속조회키
    })
    
    body = {"stk_cd": symbol}
    
    resp = requests.post(url, headers=headers, json=body)
    
    print(f"[현재가 조회 요청] symbol={symbol}, api-id=ka10004, status={resp.status_code}")
    
    if resp.status_code != 200:
        print(f"[현재가 조회 실패] symbol={symbol}, status={resp.status_code}")
        return {}

    try:
        data = resp.json()
        return_code = data.get("return_code", -1)
        return_msg = data.get("return_msg", "")
        
        print(f"[현재가 조회 응답] symbol={symbol}, return_code={return_code}, return_msg={return_msg}")
        
        # return_code 0 또는 2는 성공으로 처리 (키움 API 특성)
        if return_code not in [0, 2]:
            print(f"[현재가 조회 실패] symbol={symbol}, return_code={return_code}, return_msg={return_msg}")
            return {}
        
        # 안전한 정수 변환 함수
        def safe_int(value, default=0):
            if not value or value == "" or value is None:
                return default
            try:
                # + - 부호 제거하고 정수 변환
                clean_value = str(value).replace('+', '').replace('-', '')
                if clean_value == '' or clean_value == '0':
                    return default
                return int(clean_value)
            except (ValueError, TypeError):
                return default
        
        # 현재가 정보 추출 (호가 응답에서 현재가 추출)
        current_price = data.get("stck_prpr", "0")  # 현재가 필드
        current_price_int = safe_int(current_price)
        
        if current_price_int == 0:
            # 매수 1호가나 매도 1호가에서 현재가 추정
            buy_price = safe_int(data.get("buy_fpr_bid", "0"))
            sell_price = safe_int(data.get("sel_fpr_bid", "0"))
            
            if buy_price > 0 and sell_price > 0:
                current_price_int = (buy_price + sell_price) // 2
            elif buy_price > 0:
                current_price_int = buy_price
            elif sell_price > 0:
                current_price_int = sell_price
        
        # 현재가 정보 반환
        market_data = {
            "stck_prpr": str(current_price_int),  # 현재가
            "prdy_vrss": str(safe_int(data.get("prdy_vrss", "0"))),  # 전일대비
            "prdy_vrss_sign": data.get("prdy_vrss_sign", "3"),  # 전일대비 부호
            "prdy_ctrt": data.get("prdy_ctrt", "0.00"),  # 전일대비율
            "acml_vol": str(safe_int(data.get("acml_vol", "0"))),  # 누적거래량
        }
        
        print(f"[현재가 조회 성공] symbol={symbol}, 현재가={current_price_int}")
        return market_data
        
    except Exception as e:
        print(f"[현재가 조회 파싱 오류] {str(e)}")
        return {}


def get_10min_candles_rest(symbol: str, count: int = 50) -> pd.DataFrame:
    """
    키움증권 REST API로 분봉 조회 (ka10080: 주식분봉차트조회요청)
    :param symbol: 종목코드 (예: "005930")
    :param count: 요청할 봉 개수 (기본 50개)
    :return: pandas.DataFrame(columns=['시가','고가','저가','종가','거래량'], index=datetime)
    """
    url = f"{BASE_URL}/api/dostk/chart"
    
    headers = get_headers()
    headers.update({
        'api-id': 'ka10080',  # TR명: 주식분봉차트조회요청
        'cont-yn': 'N',       # 연속조회여부
        'next-key': ''        # 연속조회키
    })
    
    # 현재 날짜를 기준으로 조회 (YYYYMMDD 형식)
    from datetime import datetime
    today = datetime.now().strftime('%Y%m%d')
    
    body = {
        "dt": today,          # 기준일자
        "stk_cd": symbol,     # 종목코드
        "tm_unit": "10",      # 시간단위 (10분)
        "cnt": str(count)     # 조회개수
    }
    
    resp = requests.post(url, headers=headers, json=body)
    
    print(f"[10분봉 조회 요청] symbol={symbol}, count={count}, api-id=ka10080, status={resp.status_code}")
    
    if resp.status_code != 200:
        print(f"[10분봉 조회 실패] symbol={symbol}, status={resp.status_code}, body={resp.text}")
        return pd.DataFrame(columns=['시가', '고가', '저가', '종가', '거래량'])

    try:
        data = resp.json()
        return_code = data.get("return_code", -1)
        return_msg = data.get("return_msg", "")
        
        print(f"[10분봉 조회 응답] return_code={return_code}, return_msg={return_msg}")
        
        if return_code != 0:
            print(f"[10분봉 조회 실패] return_code={return_code}, return_msg={return_msg}")
            return pd.DataFrame(columns=['시가', '고가', '저가', '종가', '거래량'])
        
        # 차트 데이터 파싱 (실제 응답 구조를 확인하고 수정 필요)
        chart_data = data.get("chart_data", [])  # 실제 키 이름은 문서 확인 필요
        if not chart_data:
            print("[10분봉 조회] 데이터가 없습니다")
            return pd.DataFrame(columns=['시가', '고가', '저가', '종가', '거래량'])

        # DataFrame 생성 (실제 응답 필드명에 따라 수정 필요)
        df_list = []
        for item in chart_data:
            try:
                df_list.append({
                    'datetime': pd.to_datetime(item.get('dt') + item.get('tm', ''), format='%Y%m%d%H%M%S'),
                    '시가': int(item.get('open_prc', '0').replace('+', '').replace('-', '')),
                    '고가': int(item.get('high_prc', '0').replace('+', '').replace('-', '')),
                    '저가': int(item.get('low_prc', '0').replace('+', '').replace('-', '')),
                    '종가': int(item.get('close_prc', '0').replace('+', '').replace('-', '')),
                    '거래량': int(item.get('vol', '0'))
                })
            except (ValueError, TypeError):
                continue
        
        if df_list:
            df = pd.DataFrame(df_list)
            df.set_index('datetime', inplace=True)
            return df[["시가", "고가", "저가", "종가", "거래량"]]
        else:
            return pd.DataFrame(columns=['시가', '고가', '저가', '종가', '거래량'])
        
    except Exception as e:
        print(f"[10분봉 조회 파싱 오류] {str(e)}")
        return pd.DataFrame(columns=['시가', '고가', '저가', '종가', '거래량'])


def get_daily_candles_rest(symbol: str, count: int = 30) -> pd.DataFrame:
    """
    키움증권 REST API로 일봉 조회 (ka10081: 주식일봉차트조회요청)
    :param symbol: 종목코드 (예: "005930")
    :param count: 요청할 봉 개수 (기본 30개)
    :return: pandas.DataFrame(columns=['시가','고가','저가','종가','거래량'], index=datetime)
    """
    url = f"{BASE_URL}/api/dostk/chart"
    
    headers = get_headers()
    headers.update({
        'api-id': 'ka10081',  # TR명: 주식일봉차트조회요청
        'cont-yn': 'N',       # 연속조회여부
        'next-key': ''        # 연속조회키
    })
    
    # 현재 날짜를 기준으로 조회 (YYYYMMDD 형식)
    from datetime import datetime
    today = datetime.now().strftime('%Y%m%d')
    
    body = {
        "dt": today,          # 기준일자
        "stk_cd": symbol,     # 종목코드
        "cnt": str(count)     # 조회개수
    }
    
    resp = requests.post(url, headers=headers, json=body)
    
    print(f"[일봉 조회 요청] symbol={symbol}, count={count}, api-id=ka10081, status={resp.status_code}")
    
    if resp.status_code != 200:
        print(f"[일봉 조회 실패] symbol={symbol}, status={resp.status_code}, body={resp.text}")
        return pd.DataFrame(columns=['시가', '고가', '저가', '종가', '거래량'])

    try:
        data = resp.json()
        return_code = data.get("return_code", -1)
        return_msg = data.get("return_msg", "")
        
        print(f"[일봉 조회 응답] return_code={return_code}, return_msg={return_msg}")
        
        if return_code != 0:
            print(f"[일봉 조회 실패] return_code={return_code}, return_msg={return_msg}")
            return pd.DataFrame(columns=['시가', '고가', '저가', '종가', '거래량'])
        
        # 차트 데이터 파싱 (실제 응답 구조를 확인하고 수정 필요)
        chart_data = data.get("chart_data", [])  # 실제 키 이름은 문서 확인 필요
        if not chart_data:
            print("[일봉 조회] 데이터가 없습니다")
            return pd.DataFrame(columns=['시가', '고가', '저가', '종가', '거래량'])

        # DataFrame 생성 (실제 응답 필드명에 따라 수정 필요)
        df_list = []
        for item in chart_data:
            try:
                df_list.append({
                    'datetime': pd.to_datetime(item.get('dt'), format='%Y%m%d'),
                    '시가': int(item.get('open_prc', '0').replace('+', '').replace('-', '')),
                    '고가': int(item.get('high_prc', '0').replace('+', '').replace('-', '')),
                    '저가': int(item.get('low_prc', '0').replace('+', '').replace('-', '')),
                    '종가': int(item.get('close_prc', '0').replace('+', '').replace('-', '')),
                    '거래량': int(item.get('vol', '0'))
                })
            except (ValueError, TypeError):
                continue
        
        if df_list:
            df = pd.DataFrame(df_list)
            df.set_index('datetime', inplace=True)
            return df[["시가", "고가", "저가", "종가", "거래량"]]
        else:
            return pd.DataFrame(columns=['시가', '고가', '저가', '종가', '거래량'])
        
    except Exception as e:
        print(f"[일봉 조회 파싱 오류] {str(e)}")
        return pd.DataFrame(columns=['시가', '고가', '저가', '종가', '거래량'])


def get_orderbook_rest(symbol: str) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """
    REST API로 호가 조회 (ka10004: 주식호가요청)
    키움증권 공식 API 사용
    반환:
      - bids: [(매수호가1, 잔량1), (매수호가2, 잔량2), ...] (최대 10레벨)
      - asks: [(매도호가1, 잔량1), (매도호가2, 잔량2), ...] (최대 10레벨)
    """
    url = f"{BASE_URL}/api/dostk/mrkcond"
    
    headers = get_headers()
    headers.update({
        'api-id': 'ka10004',  # TR명: 주식호가요청
        'cont-yn': 'N',       # 연속조회여부
        'next-key': ''        # 연속조회키
    })
    
    body = {"stk_cd": symbol}
    
    resp = requests.post(url, headers=headers, json=body)
    
    print(f"[호가 조회 요청] symbol={symbol}, api-id=ka10004, status={resp.status_code}")
    
    if resp.status_code != 200:
        print(f"[호가 조회 실패] symbol={symbol}, status={resp.status_code}, body={resp.text}")
        return [], []

    try:
        data = resp.json()
        return_code = data.get("return_code", -1)
        return_msg = data.get("return_msg", "")
        
        print(f"[호가 조회 응답] return_code={return_code}, return_msg={return_msg}")
        
        if return_code != 0:
            print(f"[호가 조회 실패] return_code={return_code}, return_msg={return_msg}")
            return [], []
        
        # 안전한 정수 변환 함수
        def safe_int(value, default=0):
            if not value or value == "" or value is None:
                return default
            try:
                # + - 부호 제거하고 정수 변환
                clean_value = str(value).replace('+', '').replace('-', '')
                if clean_value == '' or clean_value == '0':
                    return default
                return int(clean_value)
            except (ValueError, TypeError):
                return default
        
        # 매수호가 파싱 (1~10차)
        bids = []
        for i in range(1, 11):
            if i == 1:
                # 최우선호가
                price_key = "buy_fpr_bid"
                qty_key = "buy_fpr_req"
            else:
                # 2~10차
                price_key = f"buy_{i}th_pre_bid"
                qty_key = f"buy_{i}th_pre_req"
            
            price = data.get(price_key, "0")
            qty = data.get(qty_key, "0")
            
            # 안전한 정수 변환
            price_int = safe_int(price)
            qty_int = safe_int(qty)
            
            if price_int > 0 and qty_int > 0:
                bids.append((price_int, qty_int))
        
        # 매도호가 파싱 (1~10차)
        asks = []
        for i in range(1, 11):
            if i == 1:
                # 최우선호가
                price_key = "sel_fpr_bid"
                qty_key = "sel_fpr_req"
            else:
                # 2~10차
                price_key = f"sel_{i}th_pre_bid"
                qty_key = f"sel_{i}th_pre_req"
            
            price = data.get(price_key, "0")
            qty = data.get(qty_key, "0")
            
            # 안전한 정수 변환
            price_int = safe_int(price)
            qty_int = safe_int(qty)
            
            if price_int > 0 and qty_int > 0:
                asks.append((price_int, qty_int))
        
        return bids, asks
        
    except Exception as e:
        print(f"[호가 조회 파싱 오류] {str(e)}")
        return [], []


# ─────────────────────────────────────────────────────────────────────────────
# 계좌 조회 API
# ─────────────────────────────────────────────────────────────────────────────

def get_holdings_rest() -> pd.DataFrame:
    """
    REST API로 보유 종목 조회 (kt00005: 체결잔고요청)
    반환:
      DataFrame(columns=['종목코드','종목명','보유수량','매입단가','현재가','평가손익'])
    """
    url = f"{BASE_URL}/api/dostk/acnt"
    
    headers = get_headers()
    headers.update({
        'api-id': 'kt00005',  # TR명: 체결잔고요청
        'cont-yn': 'N',       # 연속조회여부
        'next-key': ''        # 연속조회키
    })
    
    # kt00005 API에 필수 파라미터 추가
    body = {
        "dmst_stex_tp": "KRX"  # 국내거래소구분 (KRX, NXT, SOR)
    }
    
    resp = requests.post(url, headers=headers, json=body)
    
    print(f"[잔고 조회 요청] api-id=kt00005, status={resp.status_code}")
    print(f"[잔고 조회 응답] {resp.text}")
    
    if resp.status_code != 200:
        print(f"[잔고 조회 실패] status={resp.status_code}, body={resp.text}")
        return pd.DataFrame(columns=['종목코드', '종목명', '보유수량', '매입단가', '현재가', '평가손익'])

    try:
        data = resp.json()
        return_code = data.get("return_code", -1)
        return_msg = data.get("return_msg", "")
        
        if return_code != 0:
            print(f"[잔고 조회 실패] return_code={return_code}, return_msg={return_msg}")
            return pd.DataFrame(columns=['종목코드', '종목명', '보유수량', '매입단가', '현재가', '평가손익'])
        
        # 응답 데이터 구조를 확인하여 파싱 (실제 응답을 보고 수정 필요)
        items = data.get("data", [])  # 실제 응답 구조에 따라 수정 필요
        if not items:
            return pd.DataFrame(columns=['종목코드', '종목명', '보유수량', '매입단가', '현재가', '평가손익'])

        # 실제 응답 구조에 맞게 컬럼 매핑 (응답을 보고 수정 필요)
        df = pd.DataFrame.from_records(items).rename(columns={
            "stk_cd": "종목코드",
            "stk_nm": "종목명", 
            "qty": "보유수량",
            "avg_pric": "매입단가",
            "curr_pric": "현재가",
            "eval_pl": "평가손익"
        })
        return df[["종목코드", "종목명", "보유수량", "매입단가", "현재가", "평가손익"]]
        
    except Exception as e:
        print(f"[잔고 조회 파싱 오류] {str(e)}")
        return pd.DataFrame(columns=['종목코드', '종목명', '보유수량', '매입단가', '현재가', '평가손익'])


# ─────────────────────────────────────────────────────────────────────────────
# 주문 API
# ─────────────────────────────────────────────────────────────────────────────

def place_market_order_rest(symbol: str, side: str, qty: int, exchange: str = "KRX") -> Dict:
    """
    키움증권 REST API로 시장가 매수/매도 주문
    :param symbol: 종목코드 (예: "005930")
    :param side:   "BUY" 또는 "SELL"
    :param qty:    주문 수량 (정수)
    :param exchange: 거래소구분 (KRX, NXT, SOR - 기본값: KRX)
    :return:       응답 JSON (예: {"ord_no":"00024", "return_code":0})
    """
    url = f"{BASE_URL}/api/dostk/ordr"
    
    # TR명 결정 (매수/매도)
    api_id = "kt10000" if side.upper() == "BUY" else "kt10001"
    
    headers = get_headers()
    headers.update({
        'api-id': api_id,     # TR명: kt10000(매수) 또는 kt10001(매도)
        'cont-yn': 'N',       # 연속조회여부
        'next-key': ''        # 연속조회키
    })
    
    body = {
        "dmst_stex_tp": exchange,  # 국내거래소구분 (KRX, NXT, SOR)
        "stk_cd": symbol,          # 종목코드
        "ord_qty": str(qty),       # 주문수량 (문자열)
        "ord_uv": "",              # 주문단가 (시장가는 빈 문자열)
        "trde_tp": "3",            # 매매구분 (3: 시장가)
        "cond_uv": ""              # 조건단가 (빈 문자열)
    }
    
    resp = requests.post(url, headers=headers, json=body)
    
    print(f"[시장가 주문 요청] symbol={symbol}, side={side}, qty={qty}, api-id={api_id}, status={resp.status_code}")
    
    if resp.status_code != 200:
        print(f"[시장가 주문 실패] symbol={symbol}, side={side}, qty={qty}, status={resp.status_code}, body={resp.text}")
        return {"return_code": -1, "return_msg": f"HTTP {resp.status_code} 오류"}

    try:
        data = resp.json()
        return_code = data.get("return_code", -1)
        return_msg = data.get("return_msg", "")
        ord_no = data.get("ord_no", "")
        
        print(f"[시장가 주문 응답] return_code={return_code}, return_msg={return_msg}, ord_no={ord_no}")
        
        return data
        
    except Exception as e:
        print(f"[시장가 주문 파싱 오류] {str(e)}")
        return {"return_code": -1, "return_msg": f"파싱 오류: {str(e)}"}


def place_limit_order_rest(symbol: str, side: str, qty: int, price: int, exchange: str = "KRX") -> Dict:
    """
    키움증권 REST API로 지정가 매수/매도 주문
    :param symbol: 종목코드 (예: "005930")
    :param side:   "BUY" 또는 "SELL"
    :param qty:    주문 수량 (정수)
    :param price:  지정 가격 (정수)
    :param exchange: 거래소구분 (KRX, NXT, SOR - 기본값: KRX)
    :return:       응답 JSON
    """
    url = f"{BASE_URL}/api/dostk/ordr"
    
    # TR명 결정 (매수/매도)
    api_id = "kt10000" if side.upper() == "BUY" else "kt10001"
    
    headers = get_headers()
    headers.update({
        'api-id': api_id,     # TR명: kt10000(매수) 또는 kt10001(매도)
        'cont-yn': 'N',       # 연속조회여부
        'next-key': ''        # 연속조회키
    })
    
    body = {
        "dmst_stex_tp": exchange,  # 국내거래소구분 (KRX, NXT, SOR)
        "stk_cd": symbol,          # 종목코드
        "ord_qty": str(qty),       # 주문수량 (문자열)
        "ord_uv": str(price),      # 주문단가 (지정가)
        "trde_tp": "0",            # 매매구분 (0: 보통/지정가)
        "cond_uv": ""              # 조건단가 (빈 문자열)
    }
    
    resp = requests.post(url, headers=headers, json=body)
    
    print(f"[지정가 주문 요청] symbol={symbol}, side={side}, qty={qty}, price={price}, api-id={api_id}, status={resp.status_code}")
    
    if resp.status_code != 200:
        print(f"[지정가 주문 실패] symbol={symbol}, side={side}, qty={qty}, price={price}, status={resp.status_code}, body={resp.text}")
        return {"return_code": -1, "return_msg": f"HTTP {resp.status_code} 오류"}

    try:
        data = resp.json()
        return_code = data.get("return_code", -1)
        return_msg = data.get("return_msg", "")
        ord_no = data.get("ord_no", "")
        
        print(f"[지정가 주문 응답] return_code={return_code}, return_msg={return_msg}, ord_no={ord_no}")
        
        return data
        
    except Exception as e:
        print(f"[지정가 주문 파싱 오류] {str(e)}")
        return {"return_code": -1, "return_msg": f"파싱 오류: {str(e)}"}


def cancel_order_rest(order_id: str, symbol: str, qty: int, exchange: str = "KRX") -> Dict:
    """
    키움증권 REST API로 미체결 주문 취소 (kt10003: 주식 취소주문)
    :param order_id: 취소할 주문번호 (문자열)
    :param symbol: 종목코드 (취소 시 필요)
    :param qty: 취소 수량 (전량취소 시 원주문수량)
    :param exchange: 거래소구분 (KRX, NXT, SOR - 기본값: KRX)
    :return: 응답 JSON
    """
    url = f"{BASE_URL}/api/dostk/ordr"
    
    headers = get_headers()
    headers.update({
        'api-id': 'kt10003',  # TR명: 주식 취소주문
        'cont-yn': 'N',       # 연속조회여부
        'next-key': ''        # 연속조회키
    })
    
    body = {
        "dmst_stex_tp": exchange,  # 국내거래소구분 (KRX, NXT, SOR)
        "stk_cd": symbol,          # 종목코드
        "ord_qty": str(qty),       # 취소수량 (문자열)
        "ord_uv": "",              # 주문단가 (취소 시 빈 문자열)
        "trde_tp": "0",            # 매매구분 (취소 시 사용 안함)
        "cond_uv": "",             # 조건단가 (빈 문자열)
        "org_ord_no": order_id     # 원주문번호 (취소할 주문번호)
    }
    
    resp = requests.post(url, headers=headers, json=body)
    
    print(f"[주문 취소 요청] order_id={order_id}, symbol={symbol}, qty={qty}, status={resp.status_code}")
    
    if resp.status_code != 200:
        print(f"[주문 취소 실패] order_id={order_id}, status={resp.status_code}, body={resp.text}")
        return {"return_code": -1, "return_msg": f"HTTP {resp.status_code} 오류"}

    try:
        data = resp.json()
        return_code = data.get("return_code", -1)
        return_msg = data.get("return_msg", "")
        ord_no = data.get("ord_no", "")
        
        print(f"[주문 취소 응답] return_code={return_code}, return_msg={return_msg}, ord_no={ord_no}")
        
        return data
        
    except Exception as e:
        print(f"[주문 취소 파싱 오류] {str(e)}")
        return {"return_code": -1, "return_msg": f"파싱 오류: {str(e)}"}


def modify_order_rest(order_id: str, symbol: str, qty: int, price: int, exchange: str = "KRX") -> Dict:
    """
    키움증권 REST API로 미체결 주문 정정 (kt10002: 주식 정정주문)
    :param order_id: 정정할 주문번호 (문자열)
    :param symbol: 종목코드
    :param qty: 정정 수량
    :param price: 정정 가격
    :param exchange: 거래소구분 (KRX, NXT, SOR - 기본값: KRX)
    :return: 응답 JSON
    """
    url = f"{BASE_URL}/api/dostk/ordr"
    
    headers = get_headers()
    headers.update({
        'api-id': 'kt10002',  # TR명: 주식 정정주문
        'cont-yn': 'N',       # 연속조회여부
        'next-key': ''        # 연속조회키
    })
    
    body = {
        "dmst_stex_tp": exchange,  # 국내거래소구분 (KRX, NXT, SOR)
        "stk_cd": symbol,          # 종목코드
        "ord_qty": str(qty),       # 정정수량 (문자열)
        "ord_uv": str(price),      # 정정단가
        "trde_tp": "0",            # 매매구분 (0: 보통/지정가)
        "cond_uv": "",             # 조건단가 (빈 문자열)
        "org_ord_no": order_id     # 원주문번호 (정정할 주문번호)
    }
    
    resp = requests.post(url, headers=headers, json=body)
    
    print(f"[주문 정정 요청] order_id={order_id}, symbol={symbol}, qty={qty}, price={price}, status={resp.status_code}")
    
    if resp.status_code != 200:
        print(f"[주문 정정 실패] order_id={order_id}, status={resp.status_code}, body={resp.text}")
        return {"return_code": -1, "return_msg": f"HTTP {resp.status_code} 오류"}

    try:
        data = resp.json()
        return_code = data.get("return_code", -1)
        return_msg = data.get("return_msg", "")
        ord_no = data.get("ord_no", "")
        
        print(f"[주문 정정 응답] return_code={return_code}, return_msg={return_msg}, ord_no={ord_no}")
        
        return data
        
    except Exception as e:
        print(f"[주문 정정 파싱 오류] {str(e)}")
        return {"return_code": -1, "return_msg": f"파싱 오류: {str(e)}"}


def get_investor_chart_rest(symbol: str, date: str, amt_qty_tp: str = "1", trde_tp: str = "0") -> pd.DataFrame:
    """
    키움증권 REST API로 종목별 투자자별 매매 차트 조회 (ka10060: 종목별투자자기관별차트요청)
    :param symbol: 종목코드 (예: "005930")
    :param date: 조회일자 (YYYYMMDD 형식, 예: "20241107")
    :param amt_qty_tp: 금액수량구분 ("1": 금액, "2": 수량)
    :param trde_tp: 매매구분 ("0": 순매수, "1": 매수, "2": 매도)
    :return: pandas.DataFrame(투자자별 매매 데이터)
    """
    url = f"{BASE_URL}/api/dostk/chart"
    
    headers = get_headers()
    headers.update({
        'api-id': 'ka10060',  # TR명: 종목별투자자기관별차트요청
        'cont-yn': 'N',       # 연속조회여부
        'next-key': ''        # 연속조회키
    })
    
    body = {
        "dt": date,              # 일자 (YYYYMMDD)
        "stk_cd": symbol,        # 종목코드
        "amt_qty_tp": amt_qty_tp, # 금액수량구분 (1:금액, 2:수량)
        "trde_tp": trde_tp,      # 매매구분 (0:순매수, 1:매수, 2:매도)
        "unit_tp": "1000"        # 단위구분 (1000:천주, 1:단주)
    }
    
    resp = requests.post(url, headers=headers, json=body)
    
    print(f"[투자자차트 조회 요청] symbol={symbol}, date={date}, api-id=ka10060, status={resp.status_code}")
    
    if resp.status_code != 200:
        print(f"[투자자차트 조회 실패] symbol={symbol}, status={resp.status_code}, body={resp.text}")
        return pd.DataFrame()

    try:
        data = resp.json()
        return_code = data.get("return_code", -1)
        return_msg = data.get("return_msg", "")
        
        print(f"[투자자차트 조회 응답] return_code={return_code}, return_msg={return_msg}")
        
        if return_code != 0:
            print(f"[투자자차트 조회 실패] return_code={return_code}, return_msg={return_msg}")
            return pd.DataFrame()
        
        # 투자자별 차트 데이터 파싱
        chart_data = data.get("stk_invsr_orgn_chart", [])
        if not chart_data:
            print("[투자자차트 조회] 데이터가 없습니다")
            return pd.DataFrame()

        # DataFrame 생성
        df = pd.DataFrame(chart_data)
        
        # 날짜 컬럼을 datetime으로 변환
        if 'dt' in df.columns:
            df['dt'] = pd.to_datetime(df['dt'], format='%Y%m%d')
            df.set_index('dt', inplace=True)
        
        # 숫자 컬럼들 변환 (+ - 부호 제거)
        numeric_columns = ['cur_prc', 'pred_pre', 'acc_trde_prica', 'ind_invsr', 'frgnr_invsr', 
                          'orgn', 'fnnc_invt', 'insrnc', 'invtrt', 'etc_fnnc', 'bank', 
                          'penfnd_etc', 'samo_fund', 'natn', 'etc_corp', 'natfor']
        
        for col in numeric_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace('+', '').str.replace('-', '-').astype(float)
        
        return df
        
    except Exception as e:
        print(f"[투자자차트 조회 파싱 오류] {str(e)}")
        return pd.DataFrame()