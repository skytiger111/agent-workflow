"""
test_admin.py — 後台管理 API 端點測試

覆蓋情境：
- GET /api/admin/orders → 需管理者登入
- GET /api/admin/orders → 未登入 → 403
- GET /api/admin/orders?status=pending → 狀態篩選正確
- PUT /api/admin/orders/<id>/status → 有效狀態 → 200
- PUT /api/admin/orders/<id>/status → 無效狀態 → 400
- PUT /api/admin/orders/<id>/status → 未登入 → 403
- PUT /api/admin/orders/<id>/status → 不存在訂單 → 404
- GET /api/admin/members → 需管理者登入
- GET /api/admin/members/<id> → 需管理者登入
- GET /api/admin/members/<id>/points → 需管理者登入
- PUT /api/admin/members/<id>/points → 需管理者登入
- GET /api/reports/daily → 需管理者登入
- POST /admin/login → 登入成功 302
- POST /admin/login → 密碼錯誤 401
"""

import pytest


# ─── 管理者登入（HTML 表單）───────────────────────────────────────

class TestAdminLogin:
    """POST /admin/login — 管理者登入（Session-based）"""

    def test_admin_login_success_returns_302(self, client):
        """正確帳密 → HTTP 302 重新導向"""
        response = client.post("/admin/login", data={
            "username": "admin",
            "password": "admin123"
        }, follow_redirects=False)
        assert response.status_code == 302

    def test_admin_login_wrong_password_returns_401(self, client):
        """密碼錯誤 → HTTP 401"""
        response = client.post("/admin/login", data={
            "username": "admin",
            "password": "wrongpass"
        }, follow_redirects=False)
        assert response.status_code == 401


# ─── 管理者訂單 API ──────────────────────────────────────────────

class TestAdminOrders:
    """GET /api/admin/orders — 管理者查詢所有訂單"""

    def _create_order(self, client, checkout_payload):
        resp = client.post("/api/checkout",
                           json=checkout_payload,
                           content_type="application/json")
        return resp.get_json()["order_id"]

    def test_admin_get_orders_requires_login(self, client, checkout_payload):
        """未登入 → HTTP 403"""
        self._create_order(client, checkout_payload)
        response = client.get("/api/admin/orders")
        assert response.status_code == 403

    def test_admin_get_orders_success(self, admin_client, checkout_payload):
        """已登入管理者 → HTTP 200"""
        self._create_order(admin_client, checkout_payload)
        response = admin_client.get("/api/admin/orders")
        assert response.status_code == 200

    def test_admin_get_orders_response_fields(self, admin_client, checkout_payload):
        """Response orders 陣列中每筆包含必要欄位"""
        self._create_order(admin_client, checkout_payload)
        response = admin_client.get("/api/admin/orders")
        data = response.get_json()
        assert "orders" in data
        assert len(data["orders"]) > 0

        order = data["orders"][0]
        for field in ("id", "customer_name", "total", "status", "created_at"):
            assert field in order

    def test_admin_get_orders_filter_by_status(self, admin_client, checkout_payload):
        """?status=pending 只回傳 pending 訂單"""
        self._create_order(admin_client, checkout_payload)
        response = admin_client.get("/api/admin/orders?status=pending")
        assert response.status_code == 200
        for order in response.get_json()["orders"]:
            assert order["status"] == "pending"


class TestAdminOrderStatus:
    """PUT /api/admin/orders/<id>/status — 修改訂單狀態"""

    def _create_order(self, client, checkout_payload):
        resp = client.post("/api/checkout",
                           json=checkout_payload,
                           content_type="application/json")
        return resp.get_json()["order_id"]

    def test_admin_update_status_success(self, admin_client, checkout_payload):
        """有效狀態 → HTTP 200"""
        order_id = self._create_order(admin_client, checkout_payload)
        response = admin_client.put(
            f"/api/admin/orders/{order_id}/status",
            json={"status": "preparing"},
            content_type="application/json"
        )
        assert response.status_code == 200

    def test_admin_update_status_response_fields(self, admin_client, checkout_payload):
        """Response 包含 id、status、message"""
        order_id = self._create_order(admin_client, checkout_payload)
        response = admin_client.put(
            f"/api/admin/orders/{order_id}/status",
            json={"status": "completed"},
            content_type="application/json"
        )
        data = response.get_json()
        for field in ("id", "status", "message"):
            assert field in data

    def test_admin_update_invalid_status_returns_400(self, admin_client, checkout_payload):
        """無效狀態值 → HTTP 400"""
        order_id = self._create_order(admin_client, checkout_payload)
        response = admin_client.put(
            f"/api/admin/orders/{order_id}/status",
            json={"status": "invalid_status"},
            content_type="application/json"
        )
        assert response.status_code == 400
        assert "無效" in response.get_json().get("error", "")

    def test_admin_update_status_requires_login(self, client, checkout_payload):
        """未登入 → HTTP 403"""
        order_id = self._create_order(client, checkout_payload)
        response = client.put(
            f"/api/admin/orders/{order_id}/status",
            json={"status": "preparing"},
            content_type="application/json"
        )
        assert response.status_code == 403

    def test_admin_update_nonexistent_order_returns_404(self, admin_client):
        """不存在的 order_id → HTTP 404"""
        response = admin_client.put(
            "/api/admin/orders/999999/status",
            json={"status": "preparing"},
            content_type="application/json"
        )
        assert response.status_code == 404


# ─── 管理者會員 API ─────────────────────────────────────────────

class TestAdminMembers:
    """GET /api/admin/members — 管理者查看會員列表"""

    def test_admin_get_members_requires_login(self, client, member_data):
        """未登入 → HTTP 403"""
        # 先用一般 client 建立會員（public API 不需登入）
        client.post("/api/members/register",
                    json=member_data,
                    content_type="application/json")
        response = client.get("/api/admin/members")
        assert response.status_code == 403

    def test_admin_get_members_success(self, admin_client, member_data):
        """已登入管理者 → HTTP 200"""
        admin_client.post("/api/members/register",
                          json=member_data,
                          content_type="application/json")
        response = admin_client.get("/api/admin/members")
        assert response.status_code == 200

    def test_admin_get_members_response_fields(self, admin_client, member_data):
        """Response 包含 members 陣列，每筆有 id/name/phone/points"""
        admin_client.post("/api/members/register",
                          json=member_data,
                          content_type="application/json")
        response = admin_client.get("/api/admin/members")
        data = response.get_json()
        assert "members" in data
        assert len(data["members"]) > 0

        member = data["members"][0]
        for field in ("id", "name", "phone", "points"):
            assert field in member

    def test_admin_get_members_search_by_phone(self, admin_client, member_data):
        """?phone= 參數支援模糊搜尋"""
        admin_client.post("/api/members/register",
                          json=member_data,
                          content_type="application/json")
        prefix = member_data["phone"][:4]  # 取前四碼
        response = admin_client.get(f"/api/admin/members?phone={prefix}")
        assert response.status_code == 200
        # 所有回傳會員電話皆含此前綴
        for m in response.get_json()["members"]:
            assert prefix in m["phone"]


class TestAdminMemberDetail:
    """GET /api/admin/members/<id> — 管理者查看會員詳細資料"""

    def test_admin_get_member_detail_requires_login(self, client, member_data):
        """未登入 → HTTP 403"""
        client.post("/api/members/register",
                    json=member_data,
                    content_type="application/json")
        # 假設第一個會員 id=1（視 DB seed 而定）
        response = client.get("/api/admin/members/1")
        assert response.status_code == 403

    def test_admin_get_member_detail_success(self, admin_client, member_data):
        """已登入管理者 → HTTP 200，含 orders 與 point_history"""
        admin_client.post("/api/members/register",
                          json=member_data,
                          content_type="application/json")
        response = admin_client.get("/api/admin/members/1")
        assert response.status_code == 200
        data = response.get_json()
        for field in ("id", "name", "phone", "points", "created_at",
                     "orders", "point_history"):
            assert field in data

    def test_admin_get_nonexistent_member_returns_404(self, admin_client):
        """不存在的會員 ID → HTTP 404"""
        response = admin_client.get("/api/admin/members/999999")
        assert response.status_code == 404


class TestAdminMemberPointsAdjust:
    """PUT /api/admin/members/<id>/points — 管理者手動調整會員點數"""

    def test_admin_adjust_points_requires_login(self, client, member_data):
        """未登入 → HTTP 403"""
        client.post("/api/members/register",
                    json=member_data,
                    content_type="application/json")
        response = client.put("/api/admin/members/1/points",
                               json={"adjustment": 100, "reason": "補償"},
                               content_type="application/json")
        assert response.status_code == 403

    def test_admin_adjust_points_success(self, admin_client, member_data):
        """調整成功 → HTTP 200，含 previous_points、adjustment、new_points"""
        admin_client.post("/api/members/register",
                          json=member_data,
                          content_type="application/json")
        response = admin_client.put("/api/admin/members/1/points",
                                    json={"adjustment": 100, "reason": "補償"},
                                    content_type="application/json")
        assert response.status_code == 200
        data = response.get_json()
        for field in ("member_id", "previous_points", "adjustment",
                     "new_points", "message"):
            assert field in data
        assert data["new_points"] == data["previous_points"] + data["adjustment"]

    def test_admin_adjust_negative_points(self, admin_client, member_data):
        """adjustment 可為負數（扣點）"""
        admin_client.post("/api/members/register",
                          json=member_data,
                          content_type="application/json")
        # 先加點
        admin_client.put("/api/admin/members/1/points",
                         json={"adjustment": 100, "reason": "補償"},
                         content_type="application/json")
        # 再扣點
        response = admin_client.put("/api/admin/members/1/points",
                                   json={"adjustment": -50, "reason": "修正"},
                                   content_type="application/json")
        assert response.status_code == 200
        assert response.get_json()["new_points"] == 50

    def test_admin_adjust_missing_adjustment_returns_400(self, admin_client, member_data):
        """未提供 adjustment → HTTP 400"""
        admin_client.post("/api/members/register",
                          json=member_data,
                          content_type="application/json")
        response = admin_client.put("/api/admin/members/1/points",
                                    json={"reason": "補償"},
                                    content_type="application/json")
        assert response.status_code == 400


# ─── 日報表 ──────────────────────────────────────────────────────

class TestDailyReport:
    """GET /api/reports/daily — 每日訂單報表"""

    def test_admin_daily_report_requires_login(self, client, checkout_payload):
        """未登入 → HTTP 403"""
        client.post("/api/checkout",
                    json=checkout_payload,
                    content_type="application/json")
        response = client.get("/api/reports/daily")
        assert response.status_code == 403

    def test_admin_daily_report_success(self, admin_client, checkout_payload):
        """已登入管理者 → HTTP 200"""
        admin_client.post("/api/checkout",
                          json=checkout_payload,
                          content_type="application/json")
        response = admin_client.get("/api/reports/daily")
        assert response.status_code == 200

    def test_admin_daily_report_fields(self, admin_client, checkout_payload):
        """Response 包含 date、total_orders、total_revenue、by_status、top_items"""
        admin_client.post("/api/checkout",
                          json=checkout_payload,
                          content_type="application/json")
        response = admin_client.get("/api/reports/daily")
        data = response.get_json()
        for field in ("date", "total_orders", "total_revenue",
                     "by_status", "top_items"):
            assert field in data

    def test_admin_daily_report_filter_by_date(self, admin_client, checkout_payload):
        """/api/reports/daily?date=2026-04-17 → 只含指定日期資料"""
        admin_client.post("/api/checkout",
                          json=checkout_payload,
                          content_type="application/json")
        response = admin_client.get("/api/reports/daily?date=2026-04-17")
        assert response.status_code == 200
        assert response.get_json()["date"] == "2026-04-17"
