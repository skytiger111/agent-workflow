"""
test_menu.py — /api/menu 端點測試

覆蓋情境：
- GET /api/menu → 200，驗證結構與欄位
- 驗證 available 欄位正確（布林值）
- 驗證 menu 為陣列且至少有一項（seed data）
"""

import pytest


class TestGetMenu:
    """GET /api/menu — 取得菜單列表"""

    def test_get_menu_returns_200(self, client):
        """正常取得菜單，HTTP 200"""
        response = client.get("/api/menu")
        assert response.status_code == 200

    def test_response_has_menu_key(self, client):
        """Response JSON 包含 'menu' 鍵"""
        response = client.get("/api/menu")
        data = response.get_json()
        assert "menu" in data

    def test_menu_is_list(self, client):
        """menu 欄位為 list"""
        response = client.get("/api/menu")
        data = response.get_json()
        assert isinstance(data["menu"], list)

    def test_menu_item_has_required_fields(self, client):
        """每個品項包含必要欄位：id, name, price, category, available"""
        response = client.get("/api/menu")
        data = response.get_json()
        assert len(data["menu"]) > 0, "seed data 應至少包含一項"

        item = data["menu"][0]
        for field in ("id", "name", "price", "category", "available"):
            assert field in item, f"缺少欄位: {field}"

    def test_menu_item_types(self, client):
        """品項欄位型別正確：id/int, price/int, available/bool"""
        response = client.get("/api/menu")
        data = response.get_json()

        for item in data["menu"]:
            assert isinstance(item["id"], int), "id 應為整數"
            assert isinstance(item["price"], int), "price 應為整數"
            assert isinstance(item["available"], bool), "available 應為布林值"
            assert isinstance(item["name"], str), "name 應為字串"

    def test_available_field_values(self, client):
        """available 欄位只接受 true/false（JSON boolean）"""
        response = client.get("/api/menu")
        data = response.get_json()

        for item in data["menu"]:
            assert item["available"] in (True, False), \
                f"品項 {item['name']} 的 available 應為 true 或 false"
