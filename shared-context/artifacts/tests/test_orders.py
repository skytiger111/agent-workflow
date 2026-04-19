"""
test_orders.py — 訂單查詢 API 端點測試

覆蓋情境：
- GET /api/orders → 依 phone 查詢，回傳 orders 列表
- GET /api/orders/<id> → 取得特定訂單詳情
- GET /api/orders/<id> → 不存在的訂單 → 404
- 驗證訂單欄位結構（items, total, status, created_at）
- 驗證未提供 phone 識別時的行為（需視賽時實作調整）
"""

import pytest


class TestGetOrders:
    """GET /api/orders — 依電話查詢顧客訂單"""

    def _create_order(self, client, payload):
        """Helper：建立一筆訂單後傳回 order_id"""
        resp = client.post("/api/checkout",
                           json=payload,
                           content_type="application/json")
        return resp.get_json()["order_id"]

    def test_get_orders_returns_200(self, client, checkout_payload):
        """正常查詢回傳 HTTP 200"""
        self._create_order(client, checkout_payload)
        phone = checkout_payload["customer_phone"]
        response = client.get(f"/api/orders?phone={phone}")
        assert response.status_code == 200

    def test_get_orders_returns_list(self, client, checkout_payload):
        """Response 包含 orders 陣列"""
        self._create_order(client, checkout_payload)
        phone = checkout_payload["customer_phone"]
        response = client.get(f"/api/orders?phone={phone}")
        data = response.get_json()
        assert "orders" in data
        assert isinstance(data["orders"], list)

    def test_get_orders_contains_order_fields(self, client, checkout_payload):
        """每筆訂單包含必要欄位"""
        self._create_order(client, checkout_payload)
        phone = checkout_payload["customer_phone"]
        response = client.get(f"/api/orders?phone={phone}")
        data = response.get_json()

        assert len(data["orders"]) > 0
        order = data["orders"][0]
        required = ("id", "items", "total", "status", "created_at")
        for field in required:
            assert field in order, f"訂單缺少欄位: {field}"

    def test_get_orders_by_phone_filters_correctly(self, client, checkout_payload, member_data):
        """不同電話查詢結果不同（電話隔離）"""
        # 建立第一筆訂單
        self._create_order(client, checkout_payload)

        # 建立第二筆訂單（不同電話）
        other_payload = {
            "items": [{"id": 1, "quantity": 1}],
            "customer_name": "另一人",
            "customer_phone": "0999999999",
        }
        self._create_order(client, other_payload)

        # 以第一個電話查詢，結果應只含一筆
        resp1 = client.get(f"/api/orders?phone={checkout_payload['customer_phone']}")
        assert len(resp1.get_json()["orders"]) == 1


class TestGetOrderById:
    """GET /api/orders/<id> — 取得特定訂單詳情"""

    def test_get_order_by_id_returns_200(self, client, checkout_payload):
        """以有效 order_id 查詢 → 200"""
        # 建立訂單
        resp = client.post("/api/checkout",
                           json=checkout_payload,
                           content_type="application/json")
        order_id = resp.get_json()["order_id"]

        # 查詢
        response = client.get(f"/api/orders/{order_id}")
        assert response.status_code == 200

    def test_get_order_by_id_response_has_detail_fields(self, client, checkout_payload):
        """訂單詳情包含所有欄位"""
        resp = client.post("/api/checkout",
                           json=checkout_payload,
                           content_type="application/json")
        order_id = resp.get_json()["order_id"]

        response = client.get(f"/api/orders/{order_id}")
        data = response.get_json()
        required = ("id", "customer_name", "items", "subtotal",
                   "redeem_points", "total", "points_earned",
                   "status", "notes", "created_at")
        for field in required:
            assert field in data, f"訂單詳情缺少欄位: {field}"

    def test_get_order_by_id_not_found_returns_404(self, client):
        """不存在的 order_id → 404"""
        response = client.get("/api/orders/999999")
        assert response.status_code == 404

    def test_get_order_by_id_error_message(self, client):
        """404 Response 包含 error 訊息"""
        response = client.get("/api/orders/999999")
        data = response.get_json()
        assert "error" in data

    def test_get_order_by_id_subtotal_greater_than_or_equal_total(self, client, checkout_payload):
        """subtotal >= total + redeem_amount（subtotal = total + 折抵金額）"""
        resp = client.post("/api/checkout",
                           json=checkout_payload,
                           content_type="application/json")
        order_id = resp.get_json()["order_id"]

        response = client.get(f"/api/orders/{order_id}")
        data = response.get_json()
        assert data["subtotal"] >= data["total"]
