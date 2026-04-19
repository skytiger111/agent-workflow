# -*- coding: utf-8 -*-
"""
資料庫工具模組
提供 SQLite 連線、工廠函式、初始化及遷移功能。
"""
import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager
from flask import g, current_app

DATABASE_PATH = os.environ.get('DATABASE_PATH', 'order_system.db')


# ---------------------------------------------------------------------------
# 連線管理
# ---------------------------------------------------------------------------

def get_db():
    """取得目前請求的 DB 連線（thread-local）。"""
    if 'db' not in g:
        # 測試模式優先使用 app.config["DATABASE"]
        db_path = current_app.config.get('DATABASE', DATABASE_PATH)
        g.db = sqlite3.connect(db_path, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    """請求結束時關閉連線。"""
    db = g.pop('db', None)
    if db is not None:
        db.close()


@contextmanager
def get_db_cursor():
    """手動取得 DB 連線（用於非 Flask 上下文，如初始化腳本）。"""
    db_path = os.environ.get('DATABASE_PATH', 'order_system.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn.cursor()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
-- 現有 tables ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS menu_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price INTEGER NOT NULL,
    category TEXT,
    available INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT,
    customer_phone TEXT,
    notes TEXT,
    subtotal INTEGER NOT NULL DEFAULT 0,
    redeem_points INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    points_earned INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    menu_item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price INTEGER NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (menu_item_id) REFERENCES menu_items(id)
);

CREATE TABLE IF NOT EXISTS admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

-- 新增 tables ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    points INTEGER NOT NULL DEFAULT 0 CHECK (points >= 0),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS point_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    order_id INTEGER,
    type TEXT NOT NULL CHECK (type IN ('earn', 'redeem', 'adjust')),
    points INTEGER NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_id) REFERENCES members(id),
    FOREIGN KEY (order_id) REFERENCES orders(id)
);
"""

SEED_MENU = """
INSERT OR IGNORE INTO menu_items (name, price, category, available) VALUES
    ('牛肉麵', 150, '主食', 1),
    ('陽春麵', 80,  '主食', 1),
    ('滷味拼盤', 120, '小菜', 1),
    ('酸辣湯',  60,  '湯品', 1),
    ('豆干',    25,  '小菜', 1);
"""


def init_db():
    """使用目前 Flask app context 初始化資料庫（執行 schema）。"""
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()


def seed_menu_items():
    """寫入菜單种子資料。"""
    db = get_db()
    db.executescript(SEED_MENU)
    db.commit()


def seed_admin():
    """確保預設管理者帳戶存在且密碼已雜湊。"""
    from werkzeug.security import generate_password_hash
    db = get_db()
    cur = db.execute(
        "SELECT password_hash FROM admin_users WHERE username = 'admin'"
    )
    row = cur.fetchone()
    if row and row['password_hash'] == 'TO_BE_SET':
        hash_ = generate_password_hash('admin123')
        db.execute(
            "UPDATE admin_users SET password_hash = ? WHERE username = 'admin'",
            (hash_,)
        )
        db.commit()
    elif row is None:
        hash_ = generate_password_hash('admin123')
        db.execute(
            "INSERT INTO admin_users (username, password_hash) VALUES ('admin', ?)",
            (hash_,)
        )
        db.commit()


# ---------------------------------------------------------------------------
# 查詢輔助函式
# ---------------------------------------------------------------------------

def row_to_dict(row):
    """將 sqlite3.Row 轉為普通 dict。"""
    if row is None:
        return None
    return dict(zip(row.keys(), row))


def get_menu_items(db):
    """取得所有上架中的菜單品項。"""
    rows = db.execute(
        "SELECT id, name, price, category, available FROM menu_items WHERE available = 1"
    ).fetchall()
    return [row_to_dict(r) for r in rows]


def get_menu_item(db, item_id):
    """依 ID 取得單一菜單品項。"""
    row = db.execute(
        "SELECT id, name, price, category, available FROM menu_items WHERE id = ?",
        (item_id,)
    ).fetchone()
    return row_to_dict(row)


def get_order(db, order_id):
    """依 ID 取得訂單（含 items）。"""
    order_row = db.execute(
        "SELECT * FROM orders WHERE id = ?", (order_id,)
    ).fetchone()
    if not order_row:
        return None
    order = row_to_dict(order_row)
    item_rows = db.execute("""
        SELECT oi.quantity, oi.unit_price, m.name
        FROM order_items oi
        JOIN menu_items m ON m.id = oi.menu_item_id
        WHERE oi.order_id = ?
    """, (order_id,)).fetchall()
    order['items'] = [row_to_dict(r) for r in item_rows]
    return order


def get_member_by_phone(db, phone):
    """依電話查詢會員。"""
    row = db.execute(
        "SELECT * FROM members WHERE phone = ?", (phone,)
    ).fetchone()
    return row_to_dict(row)


def get_member(db, member_id):
    """依 ID 查詢會員。"""
    row = db.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    return row_to_dict(row)


def get_member_point_history(db, member_id):
    """取得會員點數異動歷史。"""
    rows = db.execute("""
        SELECT type, points, order_id, description, created_at
        FROM point_transactions
        WHERE member_id = ?
        ORDER BY created_at DESC
    """, (member_id,)).fetchall()
    return [row_to_dict(r) for r in rows]


def get_admin_by_username(db, username):
    """依帳號查詢管理者。"""
    row = db.execute(
        "SELECT * FROM admin_users WHERE username = ?", (username,)
    ).fetchone()
    return row_to_dict(row)
