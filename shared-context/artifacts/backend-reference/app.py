"""
Flask REST API 入口 — Market_Sentiment 後端。
"""
import logging
import uuid
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify, request, render_template

import config
import database
from crawler import get_all_crawlers
from analyzer import analyze_article

# ── Logging ──────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── Flask App ───────────────────────────────────────────────

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.from_object(config.Config)

# 初始化資料庫
database.init_db()


# ── 回應格式化 ────────────────────────────────────────────────

def ok(data: dict | list | None = None, **kwargs):
    """成功回應（200）。"""
    payload = {"code": 200, "message": "success", "data": data or kwargs}
    return jsonify(payload)


def created(message: str, data: dict | None = None, **kwargs):
    """建立成功（202）。"""
    payload = {"code": 202, "message": message, "data": data or kwargs}
    return jsonify(payload)


def error(code: int, message: str):
    """錯誤回應。"""
    return jsonify({"code": code, "message": message, "data": None}), code


# ── API 端點 ──────────────────────────────────────────────────

@app.route("/api/news", methods=["GET"])
def get_news():
    """
    最新文章列表（含情緒分數）。
    Query: source=all|cnyes|ptt|dcard, limit=20, offset=0
    """
    source = request.args.get("source", "all")
    if source not in ("all", "cnyes", "ptt", "dcard"):
        return error(400, "Invalid source: must be all/cnyes/ptt/dcard")

    try:
        limit = min(int(request.args.get("limit", 20)), 100)
    except ValueError:
        return error(400, "Invalid limit: must be integer")
    try:
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError:
        return error(400, "Invalid offset: must be integer")

    source_filter = None if source == "all" else source
    articles, total = database.get_articles(
        source=source_filter,
        limit=limit,
        offset=offset,
    )

    return ok(
        total=total,
        limit=limit,
        offset=offset,
        articles=articles,
    )


@app.route("/api/trend", methods=["GET"])
def get_trend():
    """
    情緒趨勢。
    Query: days=7|30
    """
    try:
        days = int(request.args.get("days", 7))
    except ValueError:
        return error(400, "Invalid days: must be integer")

    if days not in (7, 30):
        return error(400, "Invalid parameter: days must be 7 or 30")

    trend_data = database.get_trend(days=days)
    return ok(days=days, **trend_data)


@app.route("/api/summary", methods=["GET"])
def get_summary():
    """當日摘要統計。"""
    summary = database.get_summary()
    return ok(**summary)


@app.route("/api/crawl", methods=["POST"])
def trigger_crawl():
    """手動觸發爬蟲（非同步執行）。"""
    if database.is_crawl_running():
        return error(429, "Crawl already in progress")

    crawl_id = str(uuid.uuid4())[:8]
    thread = threading.Thread(target=_run_crawl, args=(crawl_id,))
    thread.start()

    return created("Crawl started", crawl_id=crawl_id)


def _run_crawl(crawl_id: str):
    """在背景執行爬蟲流程。"""
    from crawler import get_all_crawlers
    from analyzer import SentimentAnalyzer

    logger.info(f"[{crawl_id}] 爬蟲啟動")
    total_count = 0

    for crawler in get_all_crawlers():
        log_id = database.insert_crawl_log(crawler.source)
        articles = []
        try:
            articles = crawler.fetch(limit=20)
        except Exception as e:
            logger.error(f"[{crawl_id}] {crawler.source} 爬蟲錯誤：{e}")
            database.finish_crawl_log(log_id, status="failed")
            continue

        analyzed = 0
        for art in articles:
            try:
                result = analyze_article(art.title, art.content)
                database.upsert_article(
                    url=art.url,
                    title=art.title,
                    content=art.content,
                    source=art.source,
                    published_at=art.published_at,
                    sentiment_score=result.sentiment_score,
                    label=result.label,
                    reasoning=result.reasoning,
                )
                analyzed += 1
            except Exception as e:
                logger.warning(f"[{crawl_id}] 分析失敗 {art.url}：{e}")
                # 即使分析失敗仍寫入（使用預設分數）
                database.upsert_article(
                    url=art.url,
                    title=art.title,
                    content=art.content,
                    source=art.source,
                    published_at=art.published_at,
                )

        total_count += analyzed
        database.finish_crawl_log(log_id, status="success", article_count=analyzed)
        logger.info(f"[{crawl_id}] {crawler.source} 完成：{analyzed}/{len(articles)} 篇")

    logger.info(f"[{crawl_id}] 爬蟲全部完成，共 {total_count} 篇")


# ── 健康檢查 ─────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """健康檢查。"""
    db_ok = database.check_db_connection()
    if not db_ok:
        return error(500, "Internal server error")
    return ok(
        status="ok",
        db="connected",
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )


# ── 前端 Static ─────────────────────────────────────────────

@app.route("/")
def index():
    """前端儀表板。"""
    return render_template("index.html")


# ── 錯誤處理 ─────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return error(404, "Resource not found")


@app.errorhandler(500)
def internal_error(e):
    return error(500, "Internal server error")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])
