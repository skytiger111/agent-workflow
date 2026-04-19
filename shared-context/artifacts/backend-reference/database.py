"""
SQLite 資料庫初始化與 CRUD 操作。
"""
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Schema ────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT    NOT NULL,
    content         TEXT,
    url             TEXT    UNIQUE NOT NULL,
    source          TEXT    NOT NULL CHECK(source IN ('cnyes', 'ptt', 'dcard')),
    published_at    DATETIME,
    crawled_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sentiment_score REAL    DEFAULT 0.0,
    label           TEXT    DEFAULT 'neutral' CHECK(label IN ('positive', 'neutral', 'negative')),
    reasoning       TEXT,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_articles_crawled_at ON articles(crawled_at);

CREATE TABLE IF NOT EXISTS crawl_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT    NOT NULL,
    started_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at    DATETIME,
    article_count   INTEGER DEFAULT 0,
    status          TEXT    DEFAULT 'running' CHECK(status IN ('running', 'success', 'failed'))
);
"""


def _get_db_path() -> str:
    db_path = os.getenv("DATABASE_PATH", "data/market_sentiment.db")
    # 若為相對路徑則相對於本檔案所在目錄
    if not os.path.isabs(db_path):
        base = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base, db_path)
    return db_path


@contextmanager
def get_conn():
    """取得資料庫連線的上下文管理器。"""
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """初始化資料庫（建立 tables）。"""
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.commit()
    logger.info("資料庫初始化完成")


# ── Article CRUD ──────────────────────────────────────────────

def upsert_article(
    url: str,
    title: str,
    content: str,
    source: str,
    published_at: Optional[str],
    crawled_at: Optional[str] = None,
    sentiment_score: float = 0.0,
    label: str = "neutral",
    reasoning: str = "",
) -> int:
    """
    插入或更新文章（URL 唯一）。
    回傳文章 id。
    """
    now = crawled_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO articles
              (url, title, content, source, published_at, crawled_at,
               sentiment_score, label, reasoning)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
              title=excluded.title,
              content=excluded.content,
              published_at=excluded.published_at,
              crawled_at=excluded.crawled_at,
              sentiment_score=excluded.sentiment_score,
              label=excluded.label,
              reasoning=excluded.reasoning
        """, (url, title, content, source, published_at, now,
              sentiment_score, label, reasoning))
        conn.commit()
        return cur.lastrowid or cur.lastrowid


def get_articles(
    source: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """
    取得文章列表（分頁）。
    回傳 (articles, total_count)。
    """
    where = "WHERE source = ?" if source and source != "all" else ""
    params: list = []
    if source and source != "all":
        params.append(source)

    with get_conn() as conn:
        # total
        row = conn.execute(
            f"SELECT COUNT(*) as cnt FROM articles {where}",
            params,
        ).fetchone()
        total = row["cnt"] if row else 0

        # articles
        rows = conn.execute(
            f"""
            SELECT id, title, url, source, published_at, crawled_at,
                   sentiment_score, label, reasoning
            FROM articles
            {where}
            ORDER BY crawled_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()

    articles = [dict(r) for r in rows]
    return articles, total


def get_trend(days: int = 7) -> dict:
    """
    取得近 N 天的每日情緒趨勢。
    回傳格式：{ "trend": [{date, avg_score, count}, ...],
               "overall_avg": float, "overall_count": int }
    """
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                DATE(crawled_at) as date,
                AVG(sentiment_score) as avg_score,
                COUNT(*) as count
            FROM articles
            WHERE crawled_at >= DATE('now', ? || ' days')
            GROUP BY DATE(crawled_at)
            ORDER BY date ASC
        """, (-days,)).fetchall()

    trend = [
        {
            "date": r["date"],
            "avg_score": round(r["avg_score"] or 0.0, 4),
            "count": r["count"],
        }
        for r in rows
    ]
    overall_avg = (
        sum(t["avg_score"] * t["count"] for t in trend) / sum(t["count"] for t in trend)
        if trend else 0.0
    )
    overall_count = sum(t["count"] for t in trend)
    return {
        "trend": trend,
        "overall_avg": round(overall_avg, 4),
        "overall_count": overall_count,
    }


def get_summary() -> dict:
    """取得當日摘要。"""
    today = datetime.now(timezone.utc).date().isoformat()

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                AVG(sentiment_score) as avg_score,
                COUNT(*) as total_count,
                SUM(CASE WHEN label = 'positive' THEN 1 ELSE 0 END) as positive_count,
                SUM(CASE WHEN label = 'neutral'  THEN 1 ELSE 0 END) as neutral_count,
                SUM(CASE WHEN label = 'negative' THEN 1 ELSE 0 END) as negative_count
            FROM articles
            WHERE DATE(crawled_at) = ?
        """, (today,)).fetchall()

        source_rows = conn.execute("""
            SELECT source, COUNT(*) as cnt
            FROM articles
            WHERE DATE(crawled_at) = ?
            GROUP BY source
        """, (today,)).fetchall()

    r = rows[0] if rows else {}
    sources = {row["source"]: row["cnt"] for row in source_rows}
    return {
        "date": today,
        "avg_score": round(r["avg_score"] or 0.0, 4),
        "positive_count": r["positive_count"] or 0,
        "neutral_count": r["neutral_count"] or 0,
        "negative_count": r["negative_count"] or 0,
        "total_count": r["total_count"] or 0,
        "sources": sources,
    }


# ── Crawl Log ─────────────────────────────────────────────────

def insert_crawl_log(source: str) -> int:
    """建立爬蟲日誌（running 狀態）。"""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO crawl_logs (source, status) VALUES (?, 'running')",
            (source,),
        )
        conn.commit()
        return cur.lastrowid


def finish_crawl_log(log_id: int, status: str = "success", article_count: int = 0):
    """更新爬蟲日誌為完成狀態。"""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with get_conn() as conn:
        conn.execute(
            """UPDATE crawl_logs
               SET finished_at = ?, status = ?, article_count = ?
               WHERE id = ?""",
            (now, status, article_count, log_id),
        )
        conn.commit()


def is_crawl_running() -> bool:
    """檢查是否有爬蟲仍在執行中。"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM crawl_logs WHERE status = 'running' LIMIT 1"
        ).fetchone()
        return row is not None


def check_db_connection() -> bool:
    """檢查資料庫連線是否正常。"""
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except Exception as e:
        logger.error(f"資料庫連線失敗：{e}")
        return False
