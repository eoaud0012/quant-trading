#!/usr/bin/env python3
"""
RSI 계산 테스트 및 GUI 호환 함수
"""

import pandas as pd
import numpy as np

def compute_rsi_simple(prices, period=14):
    """
    간단한 RSI 계산 함수 (리스트 입력 가능)
    :param prices: 가격 리스트 또는 pandas Series
    :param period: RSI 기간 (기본 14)
    :return: RSI 값들의 리스트
    """
    if isinstance(prices, list):
        prices = pd.Series(prices)
    
    delta = prices.diff(1)
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)

    roll_up = up.rolling(window=period).mean()
    roll_down = down.rolling(window=period).mean()
    
    # 0으로 나누는 것 방지
    rs = roll_up / roll_down.replace(0, 1e-10)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    
    # NaN 제거하고 리스트로 반환
    rsi_list = rsi.dropna().tolist()
    return rsi_list

def test_rsi():
    """RSI 계산 테스트"""
    # 샘플 가격 데이터
    sample_prices = [
        60000, 60100, 59900, 60200, 60050, 59800, 60300, 60150,
        59950, 60400, 60250, 60100, 60500, 60350, 60200, 60600,
        60450, 60300, 60700, 60550, 60400, 60800, 60650, 60500
    ]
    
    print("=== RSI 계산 테스트 ===")
    print(f"입력 데이터: {sample_prices}")
    
    # RSI 계산
    rsi_values = compute_rsi_simple(sample_prices, period=14)
    
    print(f"RSI 값들: {rsi_values}")
    
    if len(rsi_values) > 0:
        print(f"최신 RSI: {rsi_values[-1]:.2f}")
        
        # RSI 해석
        latest_rsi = rsi_values[-1]
        if latest_rsi >= 70:
            print("📈 과매수 구간 (RSI >= 70)")
        elif latest_rsi <= 30:
            print("📉 과매도 구간 (RSI <= 30)")
        else:
            print("⚖️ 중립 구간 (30 < RSI < 70)")
    
    return rsi_values

if __name__ == "__main__":
    test_rsi() 