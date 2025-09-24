#!/usr/bin/env python3
"""
키움증권 호가창 GUI 실행 파일
"""

import sys
import os

# 현재 스크립트의 디렉토리를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from orderbook_gui import main

if __name__ == "__main__":
    main() 