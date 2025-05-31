"""
키움증권 REST API 호출 함수 모음
- 시세 조회 (캔들, 호가)
- 계좌 조회 (잔고)
- 주문 (시장가, 지정가, 취소)
"""

import requests
import pandas as pd
from typing import List, Tuple, Dict
from .config import BASE_URL
from .auth import get_headers


# ─────────────────────────────────────────────────────────────────────────────
# 시세 조회 API
# ─────────────────────────────────────────────────────────────────────────────

def get_10min_candles_rest(symbol: str, count: int = 50) -> pd.DataFrame:
    """
    REST API로 10분봉 조회 (GET /v1/market/candles/minutes/10)
      - symbol: "005930" 등 종목코드
      - count: 요청할 봉 개수 (기본 50개)
    반환: pandas.DataFrame(columns=['시가','고가','저가','종가','거래량'], index=datetime)
    """
    url = f"{BASE_URL}/v1/market/candles/minutes/10"
    resp = requests.get(url, headers=get_headers(), params={"symbol": symbol, "count": count})
    if resp.status_code != 200:
        print(f"[10분봉 조회 실패] symbol={symbol}, status={resp.status_code}, body={resp.text}")
        return pd.DataFrame()
    
    data = resp.json().get("data", [])
    if not data:
        return pd.DataFrame()

    # JSON → DataFrame 변환
    df = pd.DataFrame.from_records(data).rename(columns={
        "candle_date_time_kst": "datetime",
        "opening_price": "시가",
        "high_price": "고가",
        "low_price": "저가",
        "trade_price": "종가",
        "candle_acc_trade_volume": "거래량"
    })
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)
    return df[["시가", "고가", "저가", "종가", "거래량"]]


def get_daily_candles_rest(symbol: str, count: int = 30) -> pd.DataFrame:
    """
    REST API로 일봉 조회 (GET /v1/market/candles/days)
      - symbol: "005930" 등 종목코드
      - count: 요청할 봉 개수 (기본 30개)
    반환: pandas.DataFrame(columns=['시가','고가','저가','종가','거래량'], index=datetime)
    """
    url = f"{BASE_URL}/v1/market/candles/days"
    resp = requests.get(url, headers=get_headers(), params={"symbol": symbol, "count": count})
    if resp.status_code != 200:
        print(f"[일봉 조회 실패] symbol={symbol}, status={resp.status_code}, body={resp.text}")
        return pd.DataFrame()
    
    data = resp.json().get("data", [])
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame.from_records(data).rename(columns={
        "candle_date_time_kst": "datetime",
        "opening_price": "시가",
        "high_price": "고가",
        "low_price": "저가",
        "trade_price": "종가",
        "candle_acc_trade_volume": "거래량"
    })
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)
    return df[["시가", "고가", "저가", "종가", "거래량"]]


def get_orderbook_rest(symbol: str) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """
    REST API로 호가 5레벨 스냅샷 조회 (GET /v1/market/orderbook/levels)
    반환:
      - bids: [(매수호가1, 잔량1), (매수호가2, 잔량2), ...]
      - asks: [(매도호가1, 잔량1), (매도호가2, 잔량2), ...]
    """
    url = f"{BASE_URL}/v1/market/orderbook/levels"
    resp = requests.get(url, headers=get_headers(), params={"symbol": symbol})
    if resp.status_code != 200:
        print(f"[호가 조회 실패] symbol={symbol}, status={resp.status_code}, body={resp.text}")
        return [], []

    data = resp.json().get("data", {}).get("orderbook_units", [])
    bids = [(unit['bid_price'], unit['bid_size']) for unit in data]
    asks = [(unit['ask_price'], unit['ask_size']) for unit in data]
    return bids, asks


# ─────────────────────────────────────────────────────────────────────────────
# 계좌 조회 API
# ─────────────────────────────────────────────────────────────────────────────

def get_holdings_rest() -> pd.DataFrame:
    """
    REST API로 보유 종목 조회 (GET /v1/trading/inquiry/holdings)
    반환:
      DataFrame(columns=['종목코드','종목명','보유수량','매입단가','현재가','평가손익'])
    """
    url = f"{BASE_URL}/v1/trading/inquiry/holdings"
    resp = requests.get(url, headers=get_headers())
    if resp.status_code != 200:
        print(f"[잔고 조회 실패] status={resp.status_code}, body={resp.text}")
        return pd.DataFrame()

    items = resp.json().get("data", [])
    if not items:
        return pd.DataFrame(columns=['종목코드', '종목명', '보유수량', '매입단가', '현재가', '평가손익'])

    df = pd.DataFrame.from_records(items).rename(columns={
        "symbol": "종목코드",
        "name": "종목명",
        "quantity": "보유수량",
        "avg_price": "매입단가",
        "current_price": "현재가",
        "eval_profit": "평가손익"
    })
    return df[["종목코드", "종목명", "보유수량", "매입단가", "현재가", "평가손익"]]


# ─────────────────────────────────────────────────────────────────────────────
# 주문 API
# ─────────────────────────────────────────────────────────────────────────────

def place_market_order_rest(symbol: str, side: str, qty: int) -> Dict:
    """
    REST API로 시장가 매수/매도 주문 (POST /v1/trading/orders/market)
    :param symbol: 종목코드 (예: "005930")
    :param side:   "BUY" 또는 "SELL"
    :param qty:    주문 수량 (정수)
    :return:       응답 JSON (예: {"status":"0000","data":{"order_id":"...","...":...}})
    """
    url = f"{BASE_URL}/v1/trading/orders/market"
    body = {"symbol": symbol, "side": side, "quantity": qty}
    resp = requests.post(url, headers=get_headers(), json=body)
    if resp.status_code != 200:
        print(f"[시장가 주문 실패] symbol={symbol}, side={side}, qty={qty}, status={resp.status_code}, body={resp.text}")
        return {}
    return resp.json()


def place_limit_order_rest(symbol: str, side: str, qty: int, price: int) -> Dict:
    """
    REST API로 지정가 매수/매도 주문 (POST /v1/trading/orders/limit)
    :param symbol: 종목코드 (예: "005930")
    :param side:   "BUY" 또는 "SELL"
    :param qty:    주문 수량 (정수)
    :param price:  지정 가격 (정수)
    :return:       응답 JSON
    """
    url = f"{BASE_URL}/v1/trading/orders/limit"
    body = {"symbol": symbol, "side": side, "quantity": qty, "price": price}
    resp = requests.post(url, headers=get_headers(), json=body)
    if resp.status_code != 200:
        print(f"[지정가 주문 실패] symbol={symbol}, side={side}, qty={qty}, price={price}, status={resp.status_code}, body={resp.text}")
        return {}
    return resp.json()


def cancel_order_rest(order_id: str) -> Dict:
    """
    REST API로 미체결 주문 취소 (POST /v1/trading/orders/cancel)
    :param order_id: 취소할 주문 ID (문자열)
    :return:         응답 JSON
    """
    url = f"{BASE_URL}/v1/trading/orders/cancel"
    body = {"order_id": order_id}
    resp = requests.post(url, headers=get_headers(), json=body)
    if resp.status_code != 200:
        print(f"[주문 취소 실패] order_id={order_id}, status={resp.status_code}, body={resp.text}")
        return {}
    return resp.json() 