# -*- coding: utf-8 -*-
"""
Flask 應用程式設定
"""
import os


class Config:
    """基礎設定類別。"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DATABASE_PATH = os.environ.get('DATABASE_PATH', 'order_system.db')

    # Session 設定
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = 3600  # 1 小時

    # 測試相關（被子類覆蓋）
    TESTING = False
    DATABASE = None  # 測試模式下由 config_override 注入
