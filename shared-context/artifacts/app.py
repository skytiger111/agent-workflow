# -*- coding: utf-8 -*-
"""
點餐系統後端 Flask 應用程式
包含前台顧客 API、後台管理 API 及會員點數功能。

所有路由一覽：
  前台：GET  /api/menu
        POST /api/members/register
        POST /api/members/login
        POST /api/members/logout
        GET  /api/members/points
        POST /api/checkout
        GET  /api/orders
        GET  /api/orders/<id>
  後台：GET  /api/admin/orders
        PUT  /api/admin/orders/<id>/status
        PUT  /api/admin/members/<id>/points
        GET  /api/admin/members
        GET  /api/admin/members/<id>
        GET  /api/reports/daily
        GET  /admin/login
        POST /admin/login
        GET  /admin/orders
        POST /admin/logout
"""

import re
from datetime import date
from functools import wraps

from flask import Flask, request, jsonify, session, redirect,
                 url_for, render_template, flash, g, current_app
from werkzeug.security import generate_password_hash, check_password_hash

from database import (
    get_db, close_db,
    get_menu_items, get_menu_item, get_order,
    get_member_by_phone, get_member, get_member_point_history,
    get_admin_by_username
)


# =========================================================================
# Flask 工廠函式
# =========================================================================

def create_app(config_override=None):
    """
    Flask 應用程式工廠。
    測試時可傳入 config_override dict（如 {"TESTING": True, "DATABASE": ":memory:"}）。
    """
    app = Flask(__name__)
    app.config.from_object('config.Config')
    if config_override:
        app.config.update(config_override)

    app.teardown_appcontext(close_db)

    # 載入路由
    register_routes(app)

    return app


# =========================================================================
# 工具函式
# =========================================================================

PHONE_PATTERN = re.compile(r'^09\d{8}$')
VALID_STATUSES = {'pending', 'preparing', 'completed', 'cancelled'}


def require_member_login(f):
    """裝飾器：要求會員登入。"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'member_id' not in session:
            return jsonify({'error': '請先登入會員'}), 401
        return f(*args, **kwargs)
    return decorated


def require_admin_login(f):
    """裝飾器：要求管理者登入。"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            return jsonify({'error': '需要管理者權限'}), 403
        return f(*args, **kwargs)
    return decorated


def validate_phone(phone):
    """驗證台灣手機號碼格式。"""
    return bool(PHONE_PATTERN.match(phone))


def json_error(message, status_code):
    """回傳 JSON 錯誤。"""
    return jsonify({'error': message}), status_code


# =========================================================================
# 路由註冊
# =========================================================================

def register_routes(app):

    # ------------------------------------------------------------------
    # 前台 API
    # ------------------------------------------------------------------

    @app.route('/api/menu', methods=['GET'])
    def api_menu():
        """GET /api/menu — 取得完整菜單。"""
        db = get_db()
        items = get_menu_items(db)
        return jsonify({'menu': items})

    # ---- 會員 ----------------------------------------------------------------

    @app.route('/api/members/register', methods=['POST'])
    def api_members_register():
        """POST /api/members/register — 會員註冊。"""
        db = get_db()
        data = request.get_json() or {}

        phone = data.get('phone', '').strip()
        name = data.get('name', '').strip()
        password = data.get('password', '')

        if not name or not phone or not password:
            return json_error('姓名、電話、密碼為必填欄位', 400)
        if not validate_phone(phone):
            return json_error('電話號碼格式不正確', 400)

        existing = get_member_by_phone(db, phone)
        if existing:
            return json_error('此電話號碼已註冊', 409)

        password_hash = generate_password_hash(password)
        try:
            cur = db.execute("""
                INSERT INTO members (name, phone, password_hash, points)
                VALUES (?, ?, ?, 0)
            """, (name, phone, password_hash))
            member_id = cur.lastrowid
            db.commit()
        except Exception:
            db.rollback()
            return json_error('此電話號碼已註冊', 409)

        return jsonify({
            'member_id': member_id,
            'phone': phone,
            'name': name,
            'points': 0,
            'message': '註冊成功'
        }), 201

    @app.route('/api/members/login', methods=['POST'])
    def api_members_login():
        """POST /api/members/login — 會員登入。"""
        db = get_db()
        data = request.get_json() or {}

        phone = data.get('phone', '').strip()
        password = data.get('password', '')

        if not phone or not password:
            return json_error('電話與密碼為必填欄位', 400)

        member = get_member_by_phone(db, phone)
        if not member or not check_password_hash(member['password_hash'], password):
            return json_error('電話或密碼錯誤', 401)

        session.clear()
        session['member_id'] = member['id']
        session['member_phone'] = member['phone']
        session['member_name'] = member['name']

        return jsonify({
            'member_id': member['id'],
            'phone': member['phone'],
            'name': member['name'],
            'points': member['points'],
            'message': '登入成功'
        })

    @app.route('/api/members/logout', methods=['POST'])
    def api_members_logout():
        """POST /api/members/logout — 會員登出。"""
        session.pop('member_id', None)
        session.pop('member_phone', None)
        session.pop('member_name', None)
        return jsonify({'message': '已登出'})

    @app.route('/api/members/points', methods=['GET'])
    def api_members_points():
        """GET /api/members/points — 查詢會員當前點數（需登入）。"""
        if 'member_id' not in session:
            return json_error('請先登入會員', 401)

        db = get_db()
        member = get_member(db, session['member_id'])
        if not member:
            session.clear()
            return json_error('會員不存在', 404)

        history = get_member_point_history(db, member['id'])
        return jsonify({
            'member_id': member['id'],
            'points': member['points'],
            'history': history
        })

    # ---- 結帳 / 訂單 ---------------------------------------------------------

    @app.route('/api/checkout', methods=['POST'])
    def api_checkout():
        """
        POST /api/checkout — 顧客結帳，建立訂單（支援點數折抵）。
        點數累積/折抵與訂單建立在同一筆 transaction 中完成（原子性）。
        """
        db = get_db()
        data = request.get_json()
        if not data:
            return json_error('請求格式錯誤', 400)

        items = data.get('items', [])
        if not items:
            return json_error('請選擇至少一個品項', 400)

        customer_name = data.get('customer_name', '').strip()
        customer_phone = data.get('customer_phone', '').strip()
        notes = data.get('notes', '')
        redeem_points = data.get('redeem_points', 0)

        if not customer_name or not customer_phone:
            return json_error('顧客名稱與電話為必填欄位', 400)
        if not validate_phone(customer_phone):
            return json_error('電話號碼格式不正確', 400)

        # 取出登入會員資料（若有）
        member = None
        if 'member_id' in session:
            member = get_member(db, session['member_id'])

        # 驗證品項與計算小計
        subtotal = 0
        order_items = []
        for item in items:
            item_id = item.get('id')
            quantity = item.get('quantity', 0)
            if quantity <= 0:
                return json_error(f'品項 {item_id} 數量必須大於 0', 400)
            menu = get_menu_item(db, item_id)
            if not menu:
                return json_error(f'品項 {item_id} 不存在', 400)
            order_items.append({
                'menu_item_id': item_id,
                'quantity': quantity,
                'unit_price': menu['price']
            })
            subtotal += menu['price'] * quantity

        # 處理點數折抵
        redeem_amount = 0
        if member:
            try:
                redeem_points = int(redeem_points)
            except (TypeError, ValueError):
                return json_error('折抵點數必須為整數', 400)
            if redeem_points < 0:
                return json_error('折抵點數不得為負', 400)
            if redeem_points > 0:
                max_redeem = min(subtotal, member['points'])
                if redeem_points > max_redeem:
                    if redeem_points > subtotal:
                        return json_error('折抵點數不得超過訂單金額', 400)
                    return json_error('可折抵點數不足', 400)
                redeem_amount = redeem_points

        total = subtotal - redeem_amount
        points_earned = subtotal  # 消費 1 元累積 1 點

        try:
            cur = db.execute("""
                INSERT INTO orders
                    (customer_name, customer_phone, notes, subtotal,
                     redeem_points, total, points_earned, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (customer_name, customer_phone, notes, subtotal,
                  redeem_amount, total, points_earned))
            order_id = cur.lastrowid

            for oi in order_items:
                db.execute("""
                    INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price)
                    VALUES (?, ?, ?, ?)
                """, (order_id, oi['menu_item_id'], oi['quantity'], oi['unit_price']))

            remaining_points = None
            if member:
                new_points = member['points'] - redeem_amount + points_earned
                db.execute(
                    "UPDATE members SET points = ? WHERE id = ?",
                    (new_points, member['id'])
                )
                if points_earned > 0:
                    db.execute("""
                        INSERT INTO point_transactions
                            (member_id, order_id, type, points, description)
                        VALUES (?, ?, 'earn', ?, ?)
                    """, (member['id'], order_id, points_earned,
                          f'訂單 #{order_id} 累積點數'))
                if redeem_amount > 0:
                    db.execute("""
                        INSERT INTO point_transactions
                            (member_id, order_id, type, points, description)
                        VALUES (?, ?, 'redeem', ?, ?)
                    """, (member['id'], order_id, -redeem_amount,
                          f'訂單 #{order_id} 折抵使用'))
                remaining_points = new_points

            db.commit()

            return jsonify({
                'order_id': order_id,
                'status': 'pending',
                'subtotal': subtotal,
                'redeem_points': redeem_amount,
                'redeem_amount': redeem_amount,
                'total': total,
                'points_earned': points_earned,
                'remaining_points': remaining_points,
                'message': '訂單已送出'
            }), 201

        except Exception as e:
            db.rollback()
            return json_error(f'伺服器錯誤：{str(e)}', 500)

    @app.route('/api/orders', methods=['GET'])
    def api_orders():
        """GET /api/orders — 顧客查詢自己的訂單（以 session 或 phone 識別）。"""
        db = get_db()
        phone = request.args.get('phone')
        if 'member_phone' in session:
            phone = session['member_phone']
        if not phone:
            return jsonify({'orders': []})

        rows = db.execute("""
            SELECT id, customer_name, total, redeem_points, status, created_at
            FROM orders
            WHERE customer_phone = ?
            ORDER BY created_at DESC
        """, (phone,)).fetchall()

        orders = []
        for r in rows:
            order = dict(zip(r.keys(), r))
            item_rows = db.execute("""
                SELECT m.name, oi.quantity, oi.unit_price
                FROM order_items oi
                JOIN menu_items m ON m.id = oi.menu_item_id
                WHERE oi.order_id = ?
            """, (order['id'],)).fetchall()
            order['items'] = [dict(zip(ir.keys(), ir)) for ir in item_rows]
            orders.append(order)

        return jsonify({'orders': orders})

    @app.route('/api/orders/<int:order_id>', methods=['GET'])
    def api_order_detail(order_id):
        """GET /api/orders/<id> — 取得特定訂單詳情。"""
        db = get_db()
        order = get_order(db, order_id)
        if not order:
            return json_error('找不到訂單', 404)
        return jsonify(order)

    # ------------------------------------------------------------------
    # 後台 API（需管理者登入）
    # ------------------------------------------------------------------

    @app.route('/api/admin/orders', methods=['GET'])
    @require_admin_login
    def api_admin_orders():
        """GET /api/admin/orders — 管理者取得所有訂單（支援狀態篩選）。"""
        db = get_db()
        status = request.args.get('status')
        if status and status not in VALID_STATUSES:
            return json_error(
                '無效的狀態值，可接受：pending, preparing, completed, cancelled', 400
            )
        if status:
            rows = db.execute("""
                SELECT id, customer_name, total, status, created_at
                FROM orders WHERE status = ?
                ORDER BY created_at DESC
            """, (status,)).fetchall()
        else:
            rows = db.execute("""
                SELECT id, customer_name, total, status, created_at
                FROM orders ORDER BY created_at DESC
            """).fetchall()
        orders = [dict(zip(r.keys(), r)) for r in rows]
        return jsonify({'orders': orders})

    @app.route('/api/admin/orders/<int:order_id>/status', methods=['PUT'])
    @require_admin_login
    def api_admin_order_status(order_id):
        """PUT /api/admin/orders/<id>/status — 管理者修改訂單狀態。"""
        db = get_db()
        data = request.get_json() or {}
        new_status = data.get('status', '').strip()
        if new_status not in VALID_STATUSES:
            return json_error(
                '無效的狀態值，可接受：pending, preparing, completed, cancelled', 400
            )
        cur = db.execute("SELECT id FROM orders WHERE id = ?", (order_id,))
        if cur.fetchone() is None:
            return json_error('找不到訂單', 404)
        db.execute("UPDATE orders SET status = ? WHERE id = ?",
                   (new_status, order_id))
        db.commit()
        return jsonify({'id': order_id, 'status': new_status,
                        'message': '狀態已更新'})

    @app.route('/api/admin/members', methods=['GET'])
    @require_admin_login
    def api_admin_members():
        """GET /api/admin/members — 管理者查看會員列表（支援電話模糊搜尋）。"""
        db = get_db()
        phone = request.args.get('phone', '').strip()
        if phone:
            rows = db.execute("""
                SELECT id, name, phone, points, created_at
                FROM members WHERE phone LIKE ?
                ORDER BY created_at DESC
            """, (f'%{phone}%',)).fetchall()
        else:
            rows = db.execute("""
                SELECT id, name, phone, points, created_at
                FROM members ORDER BY created_at DESC
            """).fetchall()
        members = [dict(zip(r.keys(), r)) for r in rows]
        return jsonify({'members': members})

    @app.route('/api/admin/members/<int:member_id>', methods=['GET'])
    @require_admin_login
    def api_admin_member_detail(member_id):
        """GET /api/admin/members/<id> — 管理者查看特定會員詳細資料。"""
        db = get_db()
        member = get_member(db, member_id)
        if not member:
            return json_error('找不到會員', 404)
        order_rows = db.execute("""
            SELECT id, total, redeem_points, points_earned, status, created_at
            FROM orders WHERE customer_phone = ?
            ORDER BY created_at DESC
        """, (member['phone'],)).fetchall()
        orders = [dict(zip(r.keys(), r)) for r in order_rows]
        history = get_member_point_history(db, member_id)
        return jsonify({
            'id': member['id'],
            'name': member['name'],
            'phone': member['phone'],
            'points': member['points'],
            'created_at': member['created_at'],
            'orders': orders,
            'point_history': history
        })

    @app.route('/api/admin/members/<int:member_id>/points', methods=['PUT'])
    @require_admin_login
    def api_admin_member_adjust_points(member_id):
        """PUT /api/admin/members/<id>/points — 管理者手動調整會員點數。"""
        db = get_db()
        member = get_member(db, member_id)
        if not member:
            return json_error('找不到會員', 404)
        data = request.get_json() or {}
        adjustment = data.get('adjustment')
        if adjustment is None:
            return json_error('adjustment 為必填欄位', 400)
        try:
            adjustment = int(adjustment)
        except (TypeError, ValueError):
            return json_error('adjustment 必須為整數', 400)
        previous_points = member['points']
        new_points = previous_points + adjustment
        if new_points < 0:
            return json_error('調整後點數不得為負', 400)
        reason = data.get('reason', '管理者調整')
        try:
            db.execute("UPDATE members SET points = ? WHERE id = ?",
                       (new_points, member_id))
            db.execute("""
                INSERT INTO point_transactions
                    (member_id, order_id, type, points, description)
                VALUES (?, NULL, 'adjust', ?, ?)
            """, (member_id, adjustment, reason))
            db.commit()
        except Exception:
            db.rollback()
            return json_error('調整失敗', 500)
        return jsonify({
            'member_id': member_id,
            'previous_points': previous_points,
            'adjustment': adjustment,
            'new_points': new_points,
            'message': '點數已調整'
        })

    @app.route('/api/reports/daily', methods=['GET'])
    @require_admin_login
    def api_reports_daily():
        """GET /api/reports/daily — 管理者查看每日訂單報表。"""
        target_date = request.args.get('date') or date.today().isoformat()
        db = get_db()
        row = db.execute("""
            SELECT COUNT(*) as total_orders,
                   COALESCE(SUM(total), 0) as total_revenue
            FROM orders WHERE DATE(created_at) = ?
        """, (target_date,)).fetchone()
        status_rows = db.execute("""
            SELECT status, COUNT(*) as cnt
            FROM orders WHERE DATE(created_at) = ?
            GROUP BY status
        """, (target_date,)).fetchall()
        by_status = {r['status']: r['cnt'] for r in status_rows}
        top_rows = db.execute("""
            SELECT m.name, SUM(oi.quantity) as count
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            JOIN menu_items m ON m.id = oi.menu_item_id
            WHERE DATE(o.created_at) = ? AND o.status != 'cancelled'
            GROUP BY m.name ORDER BY count DESC LIMIT 5
        """, (target_date,)).fetchall()
        return jsonify({
            'date': target_date,
            'total_orders': row['total_orders'],
            'total_revenue': row['total_revenue'],
            'by_status': by_status,
            'top_items': [dict(zip(r.keys(), r)) for r in top_rows]
        })

    # ------------------------------------------------------------------
    # 管理頁面路由
    # ------------------------------------------------------------------

    @app.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
        """GET /admin/login — 顯示登入頁。  POST /admin/login — 提交登入。"""
        if request.method == 'GET':
            return render_template('admin_login.html')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db = get_db()
        admin = get_admin_by_username(db, username)
        if not admin or not check_password_hash(admin['password_hash'], password):
            flash('帳號或密碼錯誤')
            return redirect(url_for('admin_login'))
        session.clear()
        session['admin_id'] = admin['id']
        session['admin_username'] = admin['username']
        return redirect(url_for('admin_orders_page'))

    @app.route('/order')
    def order_page():
        """顧客點餐頁面。"""
        return render_template('order.html')

    @app.route('/admin/orders')
    def admin_orders_page():
        """管理者儀表板（需要登入）。"""
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return render_template('admin.html',
                               username=session.get('admin_username', ''))

    @app.route('/admin/logout', methods=['POST', 'GET'])
    def admin_logout():
        """管理者登出。"""
        session.pop('admin_id', None)
        session.pop('admin_username', None)
        return redirect(url_for('admin_login'))


# =========================================================================
# 啟動入口（正式環境）
# =========================================================================

app = create_app()

if __name__ == '__main__':
    from database import init_db, seed_menu_items, seed_admin
    with app.app_context():
        init_db()
        seed_menu_items()
        seed_admin()
    app.run(debug=True, host='0.0.0.0', port=5000)
