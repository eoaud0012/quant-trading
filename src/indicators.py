"""
기술적 지표 계산 함수들
- RSI (Relative Strength Index)
- 이동평균 (SMA)
- 추세 판단
"""

import pandas as pd
import numpy as np


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    pandas Series(종가) → RSI Series 반환
    :param series: 종가 시리즈 (pandas Series)
    :param period: RSI 산출 기간 (기본 14)
    """
    delta = series.diff(1)
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)

    roll_up = up.rolling(window=period).mean()
    roll_down = down.rolling(window=period).mean()
    
    # 0으로 나누는 것 방지
    rs = roll_up / roll_down.replace(0, 1e-10)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    
    return rsi


def check_daily_uptrend(df_daily: pd.DataFrame) -> bool:
    """
    일봉 DataFrame을 받아 단기 상승 추세 여부를 판단
    조건:
      1) SMA5 > SMA20
      2) 최신 종가 > SMA5
    :param df_daily: 일봉 데이터 (columns=['시가','고가','저가','종가','거래량'])
    :return: True(단기 상승 추세), False(아님)
    """
    if df_daily.empty or len(df_daily) < 20:
        return False
        
    df = df_daily.copy()
    df['SMA5'] = df['종가'].rolling(window=5).mean()
    df['SMA20'] = df['종가'].rolling(window=20).mean()

    latest = df.iloc[-1]
    if pd.isna(latest['SMA5']) or pd.isna(latest['SMA20']):
        return False

    return (latest['SMA5'] > latest['SMA20']) and (latest['종가'] > latest['SMA5'])


def calculate_moving_average(series: pd.Series, window: int) -> pd.Series:
    """
    단순 이동평균 계산
    :param series: 가격 시리즈
    :param window: 이동평균 기간
    :return: 이동평균 시리즈
    """
    return series.rolling(window=window).mean()


def calculate_bollinger_bands(series: pd.Series, window: int = 20, num_std: float = 2) -> pd.DataFrame:
    """
    볼린저 밴드 계산
    :param series: 가격 시리즈
    :param window: 이동평균 기간
    :param num_std: 표준편차 배수
    :return: DataFrame with columns ['middle', 'upper', 'lower']
    """
    sma = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    
    return pd.DataFrame({
        'middle': sma,
        'upper': sma + (std * num_std),
        'lower': sma - (std * num_std)
    }) 


# ─────────────────────────────────────────────────────────────────────────────
# 호환성을 위한 함수 별칭들
# ─────────────────────────────────────────────────────────────────────────────

# auto_trader.py에서 사용하는 함수명들에 대한 별칭
calculate_rsi = compute_rsi
simple_moving_average = calculate_moving_average 