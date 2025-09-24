#!/usr/bin/env python3
"""
종목 검색 기능 테스트
"""

from gui import STOCK_DICT, search_stocks

def test_search():
    """종목 검색 테스트"""
    print("=== 종목 검색 테스트 ===")
    print(f"현재 등록된 종목 수: {len(STOCK_DICT)}개")
    print()
    
    # 다양한 검색 테스트
    test_queries = [
        "삼성",      # 삼성 관련 종목들
        "LG",        # LG 관련 종목들
        "005930",    # 삼성전자 코드
        "카카오",     # 카카오
        "바이오",     # 바이오 관련
        "ETF",       # ETF 검색
        "게임",      # 게임 관련
        "은행",      # 은행 관련
        "에코프로",   # 에코프로 검색
        "넷마블"     # 넷마블 검색
    ]
    
    for query in test_queries:
        print(f"🔍 '{query}' 검색 결과:")
        results = search_stocks(query)
        
        if results:
            for code, name in results[:5]:  # 상위 5개만 표시
                print(f"  📈 {code}: {name}")
            if len(results) > 5:
                print(f"  ... 외 {len(results)-5}개 더")
        else:
            print("  ❌ 검색 결과 없음")
        print()

def show_categories():
    """카테고리별 종목 수 표시"""
    print("=== 카테고리별 종목 현황 ===")
    
    categories = {
        "삼성": [k for k, v in STOCK_DICT.items() if "삼성" in v],
        "LG": [k for k, v in STOCK_DICT.items() if "LG" in v or "엘지" in v],
        "SK": [k for k, v in STOCK_DICT.items() if "SK" in v],
        "현대": [k for k, v in STOCK_DICT.items() if "현대" in v or "HD" in v],
        "ETF": [k for k, v in STOCK_DICT.items() if "KODEX" in v or "TIGER" in v or "ARIRANG" in v],
        "바이오": [k for k, v in STOCK_DICT.items() if "바이오" in v or "제약" in v or "약품" in v],
        "게임": [k for k, v in STOCK_DICT.items() if "게임" in v or "엔터" in v],
        "금융": [k for k, v in STOCK_DICT.items() if "금융" in v or "은행" in v or "증권" in v or "카드" in v],
    }
    
    for category, codes in categories.items():
        print(f"{category} 관련: {len(codes)}개")
        for code in codes[:3]:  # 상위 3개만 표시
            print(f"  - {code}: {STOCK_DICT[code]}")
        if len(codes) > 3:
            print(f"  ... 외 {len(codes)-3}개 더")
        print()

if __name__ == "__main__":
    test_search()
    show_categories() 