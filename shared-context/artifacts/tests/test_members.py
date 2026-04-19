"""
test_members.py — 會員相關 API 端點測試

覆蓋情境：
- POST /api/members/register → 201，成功註冊
- POST /api/members/register → 409，電話已註冊
- POST /api/members/register → 400，電話格式錯誤
- POST /api/members/login → 200，登入成功
- POST /api/members/login → 401，密碼錯誤
- GET /api/members/points → 200（需登入）
- GET /api/members/points → 401（未登入）
- 點數累積後查詢 history 有 earn 記錄
"""

import pytest


class TestMemberRegister:
    """POST /api/members/register — 會員註冊"""

    def test_register_returns_201(self, client, member_data):
        """成功註冊回應 HTTP 201"""
        response = client.post("/api/members/register",
                               json=member_data,
                               content_type="application/json")
        assert response.status_code == 201

    def test_register_response_fields(self, client, member_data):
        """Response 包含 member_id、phone、name、points、message"""
        response = client.post("/api/members/register",
                               json=member_data,
                               content_type="application/json")
        data = response.get_json()
        for field in ("member_id", "phone", "name", "points", "message"):
            assert field in data, f"缺少欄位: {field}"

    def test_register_initial_points_are_zero(self, client, member_data):
        """新會員初始點數為 0"""
        response = client.post("/api/members/register",
                               json=member_data,
                               content_type="application/json")
        assert response.get_json()["points"] == 0

    def test_register_duplicate_phone_returns_409(self, client, member_data):
        """電話已註冊 → HTTP 409"""
        client.post("/api/members/register",
                    json=member_data,
                    content_type="application/json")
        response = client.post("/api/members/register",
                               json=member_data,
                               content_type="application/json")
        assert response.status_code == 409
        assert "已註冊" in response.get_json().get("error", "")

    def test_register_invalid_phone_format_returns_400(self, client):
        """電話格式錯誤（不是 09xx 開頭或長度不對）→ 400"""
        invalid_phones = ["123456", "abcd", "088888888", "09123456789"]
        for phone in invalid_phones:
            payload = {
                "phone": phone,
                "name": "測試",
                "password": "test1234"
            }
            response = client.post("/api/members/register",
                                  json=payload,
                                  content_type="application/json")
            assert response.status_code == 400, f"電話 {phone} 應回傳 400"

    def test_register_missing_fields_returns_400(self, client):
        """缺少任一必填欄位 → 400"""
        incomplete = [
            {"phone": "0912345678"},           # 缺 name, password
            {"name": "張三", "password": "x"},   # 缺 phone
            {"phone": "0912345678", "name": "張三"},  # 缺 password
        ]
        for payload in incomplete:
            response = client.post("/api/members/register",
                                   json=payload,
                                   content_type="application/json")
            assert response.status_code == 400


class TestMemberLogin:
    """POST /api/members/login — 會員登入"""

    def test_login_success_returns_200(self, client, member_data):
        """正確帳密登入 → HTTP 200"""
        # 先註冊
        client.post("/api/members/register",
                    json=member_data,
                    content_type="application/json")
        # 登入
        response = client.post("/api/members/login",
                               json={"phone": member_data["phone"],
                                     "password": member_data["password"]},
                               content_type="application/json")
        assert response.status_code == 200

    def test_login_success_response_fields(self, client, member_data):
        """登入成功回應包含 member_id、phone、name、points"""
        client.post("/api/members/register",
                    json=member_data,
                    content_type="application/json")
        response = client.post("/api/members/login",
                               json={"phone": member_data["phone"],
                                     "password": member_data["password"]},
                               content_type="application/json")
        data = response.get_json()
        for field in ("member_id", "phone", "name", "points", "message"):
            assert field in data

    def test_login_wrong_password_returns_401(self, client, member_data):
        """密碼錯誤 → HTTP 401"""
        client.post("/api/members/register",
                    json=member_data,
                    content_type="application/json")
        response = client.post("/api/members/login",
                               json={"phone": member_data["phone"],
                                     "password": "wrongpassword"},
                               content_type="application/json")
        assert response.status_code == 401
        assert "錯誤" in response.get_json().get("error", "")

    def test_login_unregistered_phone_returns_401(self, client):
        """電話未註冊 → HTTP 401"""
        response = client.post("/api/members/login",
                               json={"phone": "0919999999",
                                     "password": "anypass"},
                               content_type="application/json")
        assert response.status_code == 401


class TestMemberPoints:
    """GET /api/members/points — 會員點數查詢"""

    def test_get_points_requires_login(self, client):
        """未登入 → HTTP 401"""
        response = client.get("/api/members/points")
        assert response.status_code == 401

    def test_get_points_logged_in_returns_200(self, registered_member_client):
        """已登入 → HTTP 200"""
        response = registered_member_client.get("/api/members/points")
        assert response.status_code == 200

    def test_get_points_response_fields(self, registered_member_client):
        """Response 包含 member_id、points、history"""
        response = registered_member_client.get("/api/members/points")
        data = response.get_json()
        for field in ("member_id", "points", "history"):
            assert field in data

    def test_get_points_history_is_list(self, registered_member_client):
        """history 為 list"""
        response = registered_member_client.get("/api/members/points")
        data = response.get_json()
        assert isinstance(data["history"], list)

    def test_points_after_checkout_has_earn_history(
        self, registered_member_client, member_data, sample_menu_item
    ):
        """結帳後查詢點數，history 中有 earn 記錄"""
        # 結帳
        registered_member_client.post("/api/checkout",
                                      json={
                                          "items": [sample_menu_item],
                                          "customer_name": member_data["name"],
                                          "customer_phone": member_data["phone"],
                                      },
                                      content_type="application/json")
        # 查詢點數
        response = registered_member_client.get("/api/members/points")
        data = response.get_json()

        earn_records = [h for h in data["history"] if h["type"] == "earn"]
        assert len(earn_records) > 0, "應有至少一筆記帳記錄"

    def test_points_after_checkout_matches_earned(
        self, registered_member_client, member_data, sample_menu_item
    ):
        """結帳後 points 總額正確（= 本次 earned）"""
        # 結帳
        checkout_resp = registered_member_client.post(
            "/api/checkout",
            json={
                "items": [sample_menu_item],
                "customer_name": member_data["name"],
                "customer_phone": member_data["phone"],
            },
            content_type="application/json"
        )
        earned = checkout_resp.get_json()["points_earned"]

        # 查詢點數
        points_resp = registered_member_client.get("/api/members/points")
        points_data = points_resp.get_json()
        assert points_data["points"] == earned
