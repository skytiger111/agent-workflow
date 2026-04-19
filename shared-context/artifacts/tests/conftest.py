"""
conftest.py — pytest 全域 fixture 與測試環境設定

測試策略：
- 每個測試使用獨立的記憶體 SQLite（:memory:），確保完全隔離
- 透過 app.config["DATABASE"] = ":memory:" 注入，避免汙染正式資料庫
- 自動初始化 DB schema 與种子資料（menu items、admin user）
- admin_client / registered_member_client fixture 提供已認證的 client

⚠️ 注意：此檔案需複製至 {project_root}/tests/conftest.py 才能正常執行 pytest
"""

import pytest
import sys
import os

# 確保專案根目錄在 import path 中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def app():
    """
    建立測試用 Flask app，使用 :memory: SQLite 隔離資料庫。
    每個測試函式都會獲得一個乾淨的 app instance。
    """
    from app import create_app
    from database import init_db, seed_menu_items, seed_admin

    test_app = create_app()
    test_app.config.update({
        "TESTING": True,
        "DATABASE": ":memory:",
        "SECRET_KEY": "test-secret-key-for-testing-only",
        "WTF_CSRF_ENABLED": False,
    })

    with test_app.app_context():
        init_db()
        seed_menu_items()
        seed_admin()

    yield test_app


@pytest.fixture
def client(app):
    """Flask 測試 client，支援 .post() / .get() 發送 HTTP 請求。"""
    return app.test_client()


@pytest.fixture
def app_context(app):
    """手動推送 app_context，適用於直接操作 DB connection 的測試。"""
    with app.app_context():
        yield


# ─── 認證 fixture ───────────────────────────────────────────────

@pytest.fixture
def admin_client(client):
    """已登入管理者的 client。預設帳號：admin / admin123"""
    client.post("/admin/login", data={
        "username": "admin",
        "password": "admin123"
    }, follow_redirects=True)
    return client


@pytest.fixture
def member_data():
    """測試用會員資料（不寫入 DB）。"""
    return {
        "phone": "0988888888",
        "name": "測試會員",
        "password": "testpass123"
    }


@pytest.fixture
def registered_member_client(client, member_data):
    """
    已註冊並登入的會員 client。
    session 中會攜帶 member_id，可直接存取 /api/members/* 端點。
    """
    # 註冊
    client.post("/api/members/register",
                json=member_data,
                content_type="application/json")
    # 登入
    client.post("/api/members/login",
                json={
                    "phone": member_data["phone"],
                    "password": member_data["password"]
                },
                content_type="application/json")
    return client


# ─── 資料 fixture ─────────────────────────────────────────────

@pytest.fixture
def sample_menu_item():
    """標準測試用菜單品項（seed 後 id=1 為「牛肉麵」）。"""
    return {"id": 1, "quantity": 2}


@pytest.fixture
def checkout_payload(sample_menu_item, member_data):
    """標準結帳 request body。"""
    return {
        "items": [sample_menu_item],
        "customer_name": member_data["name"],
        "customer_phone": member_data["phone"],
        "notes": "不要蔥"
    }
