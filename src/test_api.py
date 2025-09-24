#!/usr/bin/env python3
"""
API 테스트 스크립트 - 키움 API 응답 상세 확인
"""

import requests
import json
from auth import get_headers, initialize_auth
from config import BASE_URL

def test_major_stocks():
    """메이저 종목들로 테스트"""
    print("=== 메이저 종목 테스트 ===")
    
    # 토큰 초기화
    print("토큰 초기화 중...")
    initialize_auth()
    print("토큰 초기화 완료!")
    
    # 메이저 종목으로 테스트
    test_symbols = [
        ("005930", "삼성전자"),
        ("000660", "SK하이닉스"), 
        ("035420", "NAVER"),
        ("373220", "LG에너지솔루션"),
        ("207940", "자이언트스텝"),
        ("091990", "셀트리온헬스케어"),
        ("096770", "SK이노베이션"),
        ("069500", "KODEX 200"),
        ("003490", "대한항공"),
        ("005380", "현대차")
    ]
    
    for symbol, name in test_symbols:
        print(f"\n--- {symbol} ({name}) ---")
        
        url = f"{BASE_URL}/api/dostk/mrkcond"
        
        headers = get_headers()
        headers.update({
            'api-id': 'ka10004',
            'cont-yn': 'N',
            'next-key': ''
        })
        
        body = {"stk_cd": symbol}
        
        try:
            resp = requests.post(url, headers=headers, json=body)
            
            if resp.status_code == 200:
                data = resp.json()
                return_code = data.get("return_code", -1)
                
                if return_code == 0:
                    # 데이터 확인
                    current_price = data.get("stck_prpr", "")
                    buy_price = data.get("buy_fpr_bid", "")
                    sell_price = data.get("sel_fpr_bid", "")
                    
                    has_data = False
                    if current_price and current_price != "":
                        print(f"  현재가: {current_price}")
                        has_data = True
                    if buy_price and buy_price != "":
                        print(f"  매수호가: {buy_price}")
                        has_data = True
                    if sell_price and sell_price != "":
                        print(f"  매도호가: {sell_price}")
                        has_data = True
                        
                    if not has_data:
                        print("  ⚠️  데이터 없음 (거래시간 외)")
                    else:
                        print("  ✅ 데이터 있음")
                else:
                    print(f"  ❌ 실패: {data.get('return_msg', '')}")
            else:
                print(f"  HTTP 오류: {resp.status_code}")
                
        except Exception as e:
            print(f"  오류: {e}")

def test_chart_api():
    """차트 API 테스트"""
    print("\n=== 차트 API 테스트 ===")
    
    url = f"{BASE_URL}/api/dostk/chart"
    
    headers = get_headers()
    headers.update({
        'api-id': 'ka10081',  # 일봉 차트
        'cont-yn': 'N',
        'next-key': ''
    })
    
    from datetime import datetime
    today = datetime.now().strftime('%Y%m%d')
    
    body = {
        "dt": today,
        "stk_cd": "005930",  # 삼성전자
        "cnt": "5"
    }
    
    try:
        resp = requests.post(url, headers=headers, json=body)
        
        if resp.status_code == 200:
            data = resp.json()
            return_code = data.get("return_code", -1)
            return_msg = data.get("return_msg", "")
            
            print(f"차트 API: return_code={return_code}, msg={return_msg}")
            
            if return_code == 0:
                print("✅ 차트 API 성공!")
                # 응답 구조 확인
                print("응답 키들:", list(data.keys()))
            else:
                print("❌ 차트 API 실패")
                print("전체 응답:", json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"HTTP 오류: {resp.status_code}")
            
    except Exception as e:
        print(f"차트 API 오류: {e}")

if __name__ == "__main__":
    test_major_stocks()
    test_chart_api() 