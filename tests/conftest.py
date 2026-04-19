# -*- coding: utf-8 -*-
"""tests/conftest.py — pytest 全域 fixture 與路徑設定"""
import os, sys

# 將專案根目錄加入 sys.path，讓子目錄測試能正確 import app
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
