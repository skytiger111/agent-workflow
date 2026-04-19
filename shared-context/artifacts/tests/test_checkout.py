"""
test_checkout.py — POST /api/checkout 端點測試

覆蓋情境：
- 正常結帳（無會員）→ 201，含 order_id、status、subtotal、total、points_earned
- 正常結帳（會員）→ 201，points_earned 正確，remaining_points 正確
- 會員點數折抵（部分）→ 驗證 redeem_points、redeem_amount 正確
- 會員點數折抵（全額）→ 折抵點數 = subtotal 時，total = 0
- 錯誤：品項 ID 不存在 → 400
- 錯誤：數量為零 → 400
- 錯誤：折抵點數超過訂單金額 → 400
- 錯誤：折抵點數超過可用點數 → 400
- 錯誤：缺少必填欄位 → 400
"""

import pytest


class TestCheckoutSuccess:
    """POST /api/checkout — 正常結帳流程"""

    def test_checkout_returns_201(self, client, checkout_payload):
        """建立訂單成功，回應 HTTP 201"""
        response = client.post("/api/checkout",
                                json=checkout_payload,
                                content_type="application/json")
        assert response.status_code == 201

    def test_checkout_response_has_required_fields(self, client, checkout_payload):
        """Response 包含所有必要欄位"""
        response = client.post("/api/checkout",
                                json=checkout_payload,
                                content_type="application/json")
        data = response.get_json()
        required = ("order_id", "status", "subtotal", "total",
                    "points_earned", "message")
        for field in required:
            assert field in data, f"缺少欄位: {field}"

    def test_checkout_points_earned_equals_subtotal(self, client, checkout_payload):
        """消費 1 元累積 1 點：points_earned == subtotal"""
        response = client.post("/api/checkout",
                                json=checkout_payload,
                                content_type="application/json")
        data = response.get_json()
        assert data["points_earned"] == data["subtotal"]

    def test_checkout_order_id_is_integer(self, client, checkout_payload):
        """order_id 為整數，可供後續查詢"""
        response = client.post("/api/checkout",
                                json=checkout_payload,
                                content_type="application/json")
        data = response.get_json()
        assert isinstance(data["order_id"], int)

    def test_checkout_status_is_pending(self, client, checkout_payload):
        """新訂單狀態預設為 pending"""
        response = client.post("/api/checkout",
                                json=checkout_payload,
                                content_type="application/json")
        data = response.get_json()
        assert data["status"] == "pending"


class TestCheckoutMemberWithPoints:
    """POST /api/checkout — 會員結帳，含點數累積與折抵"""

    def test_member_checkout_earns_points(self, registered_member_client, member_data, sample_menu_item):
        """會員結帳後 points_earned 正確（subtotal），remaining_points 增加"""
        payload = {
            "items": [sample_menu_item],
            "customer_name": member_data["name"],
            "customer_phone": member_data["phone"],
        }
        response = registered_member_client.post(
            "/api/checkout", json=payload, content_type="application/json"
        )
        data = response.get_json()
        assert data["points_earned"] == data["subtotal"]
        # 結帳後剩餘點數 = 原有點數(0) + earned
        assert "remaining_points" in data

    def test_member_redeem_partial_points(self, registered_member_client,
                                          member_data, sample_menu_item):
        """
        會員折抵部分點數：redeem_points <= subtotal 且 <= 可用點數
        redeem_amount == redeem_points，total == subtotal - redeem_points
        """
        # 先結帳一筆，累積點數
        first_payload = {
            "items": [sample_menu_item],
            "customer_name": member_data["name"],
            "customer_phone": member_data["phone"],
        }
        first_resp = registered_member_client.post(
            "/api/checkout", json=first_payload, content_type="application/json"
        )
        earned = first_resp.get_json()["points_earned"]

        # 第二筆使用部分點數折抵
        redeem = min(earned, 50)
        second_payload = {
            "items": [{"id": sample_menu_item["id"], "quantity": 1}],
            "customer_name": member_data["name"],
            "customer_phone": member_data["phone"],
            "redeem_points": redeem,
        }
        second_resp = registered_member_client.post(
            "/api/checkout", json=second_payload, content_type="application/json"
        )
        data = second_resp.get_json()

        assert data["redeem_points"] == redeem
        assert data["redeem_amount"] == redeem
        assert data["total"] == data["subtotal"] - redeem

    def test_redeem_exceeds_order_amount_returns_400(self, registered_member_client,
                                                      member_data, sample_menu_item):
        """折抵點數超過訂單金額 → 400"""
        # 先累積足夠點數
        registered_member_client.post("/api/checkout",
                                       json={"items": [sample_menu_item],
                                             "customer_name": member_data["name"],
                                             "customer_phone": member_data["phone"]},
                                       content_type="application/json")

        # 嘗試折抵一個超大數值（遠超 subtotal）
        payload = {
            "items": [{"id": sample_menu_item["id"], "quantity": 1}],
            "customer_name": member_data["name"],
            "customer_phone": member_data["phone"],
            "redeem_points": 999999,
        }
        response = registered_member_client.post(
            "/api/checkout", json=payload, content_type="application/json"
        )
        assert response.status_code == 400
        assert "超過" in response.get_json().get("error", "")

    def test_redeem_exceeds_available_points_returns_400(self, registered_member_client,
                                                          member_data, sample_menu_item):
        """折抵點數超過帳戶可用點數 → 400"""
        # 尚未累積任何點數，嘗試折抵
        payload = {
            "items": [sample_menu_item],
            "customer_name": member_data["name"],
            "customer_phone": member_data["phone"],
            "redeem_points": 100,
        }
        response = registered_member_client.post(
            "/api/checkout", json=payload, content_type="application/json"
        )
        assert response.status_code == 400
        assert "不足" in response.get_json().get("error", "")


class TestCheckoutValidation:
    """POST /api/checkout — 參數驗證錯誤"""

    def test_invalid_item_id_returns_400(self, client, member_data):
        """品項 ID 不存在 → 400"""
        payload = {
            "items": [{"id": 99999, "quantity": 1}],
            "customer_name": member_data["name"],
            "customer_phone": member_data["phone"],
        }
        response = client.post("/api/checkout",
                                json=payload,
                                content_type="application/json")
        assert response.status_code == 400

    def test_zero_quantity_returns_400(self, client, sample_menu_item, member_data):
        """數量為零 → 400"""
        payload = {
            "items": [{"id": sample_menu_item["id"], "quantity": 0}],
            "customer_name": member_data["name"],
            "customer_phone": member_data["phone"],
        }
        response = client.post("/api/checkout",
                                json=payload,
                                content_type="application/json")
        assert response.status_code == 400

    def test_missing_required_fields_returns_400(self, client):
        """缺少 customer_name、customer_phone、items 任一必填欄位 → 400"""
        incomplete_payloads = [
            {},  # 完全空白
            {"items": [{"id": 1, "quantity": 1}]},  # 缺少 customer_name/phone
            {"customer_name": "測試", "customer_phone": "0912345678"},  # 缺少 items
        ]
        for payload in incomplete_payloads:
            response = client.post("/api/checkout",
                                    json=payload,
                                    content_type="application/json")
            assert response.status_code == 400, f"Payload {payload} 應回傳 400"

    def test_empty_items_returns_400(self, client, member_data):
        """items 為空陣列 → 400"""
        payload = {
            "items": [],
            "customer_name": member_data["name"],
            "customer_phone": member_data["phone"],
        }
        response = client.post("/api/checkout",
                                json=payload,
                                content_type="application/json")
        assert response.status_code == 400
