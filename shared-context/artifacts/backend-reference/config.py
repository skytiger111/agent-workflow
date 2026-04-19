"""
環境變數讀取與應用程式設定。
"""
import os
from dotenv import load_dotenv

# 載入 .env 檔案（若存在）
load_dotenv()


class Config:
    """Flask 應用程式設定。"""

    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = FLASK_ENV == "development"

    # 資料庫
    DATABASE_PATH = os.getenv("DATABASE_PATH", "data/market_sentiment.db")

    # LLM API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

    # 爬蟲設定
    CRAWL_DELAY_SECONDS = float(os.getenv("CRAWL_DELAY_SECONDS", "1.5"))
