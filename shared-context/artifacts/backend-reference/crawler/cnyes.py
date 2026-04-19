"""
鉅亨網爬蟲 — https://news.cnyes.com/news/category/headline
"""
import random
import time
import logging
from datetime import datetime
from typing import List

import requests
from bs4 import BeautifulSoup

from crawler.base import BaseCrawler, Article

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html",
    "Referer": "https://news.cnyes.com/",
}


class CnyesCrawler(BaseCrawler):
    """鉅亨網頭條新聞爬蟲。"""

    BASE_URL = "https://news.cnyes.com/news/category/headline"

    @property
    def source(self) -> str:
        return "cnyes"

    def fetch(self, limit: int = 20) -> List[Article]:
        """
        爬取鉅亨網頭條新聞。
        每頁 20 筆，最多爬取 3 頁（60 筆）。
        """
        articles: List[Article] = []
        pages = min(3, (limit + 19) // 20)

        for page in range(1, pages + 1):
            url = f"{self.BASE_URL}?page={page}"
            try:
                resp = requests.get(url, headers=HEADERS, timeout=10)
                if resp.status_code == 429:
                    logger.warning("鉅亨網 429，等待 30 秒後重試")
                    time.sleep(30)
                    resp = requests.get(url, headers=HEADERS, timeout=10)
                if resp.status_code != 200:
                    logger.warning(f"鉅亨網 HTTP {resp.status_code}，略過 page={page}")
                    continue

                data = resp.json()
                items = data.get("items", []) or data.get("data", [])

                for item in items:
                    article = self._parse_item(item)
                    if article:
                        articles.append(article)

                # 反爬：每頁間隔 1-3 秒隨機延遲
                if page < pages:
                    time.sleep(random.uniform(1, 3))

            except requests.Timeout:
                logger.warning(f"鉅亨網 page={page} 連線逾時，略過")
            except Exception as e:
                logger.error(f"鉅亨網 page={page} 錯誤：{e}")

            if len(articles) >= limit:
                break

        return articles[:limit]

    def _parse_item(self, item: dict) -> Article | None:
        """解析單筆新聞項目。"""
        try:
            title = (item.get("title") or item.get("summary") or "").strip()
            if not title:
                return None

            url = item.get("url", "")
            if not url.startswith("http"):
                url = f"https://news.cnyes.com{url}"

            content = (
                item.get("content", "") or item.get("summary", "")
            )
            # 取前 500 字
            content = content[:500]

            # 發布時間（嘗試解析多種格式）
            pub_str = item.get("publishedAt") or item.get("published_at") or ""
            published_at = self._parse_datetime(pub_str)

            return Article(
                url=url,
                title=title,
                content=content,
                published_at=published_at,
                source=self.source,
            )
        except Exception as e:
            logger.warning(f"解析鉅亨網文章失敗：{e}")
            return None

    def _parse_datetime(self, raw: str) -> str:
        """將多種日期格式轉為 ISO 8601。"""
        if not raw:
            return datetime.utcnow().isoformat() + "Z"

        # 移除時區資訊中的常見格式
        raw = raw.replace("+08:00", "").replace("T+8:00", "")

        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.isoformat().replace("+00:00", "Z")
        except Exception:
            try:
                dt = datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S")
                return dt.isoformat() + "Z"
            except Exception:
                return datetime.utcnow().isoformat() + "Z"
