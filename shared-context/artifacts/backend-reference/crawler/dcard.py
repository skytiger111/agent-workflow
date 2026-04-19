"""
Dcard 台股版爬蟲 — https://www.dcard.tw/service/api/v2/posts?forum=stock&limit=30
"""
import random
import time
import logging
from datetime import datetime
from typing import List, Optional

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
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.dcard.tw/",
}


class DcardCrawler(BaseCrawler):
    """Dcard 台股版爬蟲。"""

    BASE_URL = "https://www.dcard.tw/service/api/v2/posts"
    FORUM = "stock"

    @property
    def source(self) -> str:
        return "dcard"

    def fetch(self, limit: int = 30) -> List[Article]:
        """使用 Dcard REST API 爬取台股版文章。"""
        articles: List[Article] = []
        collected = 0
        last_id: Optional[str] = None
        pages = min(3, (limit + 29) // 30)

        for _ in range(pages):
            params = {
                "forum": self.FORUM,
                "limit": 30,
            }
            if last_id:
                params["before"] = last_id

            try:
                resp = requests.get(
                    self.BASE_URL,
                    params=params,
                    headers=HEADERS,
                    timeout=10,
                )
                if resp.status_code == 429:
                    logger.warning("Dcard 429，等待 30 秒後重試")
                    time.sleep(30)
                    resp = requests.get(
                        self.BASE_URL,
                        params=params,
                        headers=HEADERS,
                        timeout=10,
                    )
                if resp.status_code != 200:
                    logger.warning(f"Dcard HTTP {resp.status_code}，略過")
                    break

                items = resp.json()
                if not items:
                    break

                for item in items:
                    article = self._parse_item(item)
                    if article:
                        articles.append(article)
                        collected += 1
                        if collected >= limit:
                            return articles[:limit]

                last_id = str(items[-1].get("id", ""))
                time.sleep(random.uniform(1, 2))

            except requests.Timeout:
                logger.warning("Dcard 連線逾時，略過")
                break
            except Exception as e:
                logger.error(f"Dcard 爬蟲錯誤：{e}")
                break

        return articles[:limit]

    def _parse_item(self, item: dict) -> Article | None:
        """解析單筆 Dcard 文章。"""
        try:
            title = (item.get("title") or "").strip()
            if not title:
                return None

            url = item.get("postURL") or f"https://www.dcard.tw/p/Stock/post/{item.get('id')}"
            if not url.startswith("http"):
                url = f"https://www.dcard.tw{url}"

            content = (item.get("excerpt") or item.get("content") or "")[:500]

            # Dcard API 回傳的時間格式
            created_at_raw = item.get("createdAt") or item.get("created_at") or ""
            published_at = self._parse_datetime(created_at_raw)

            return Article(
                url=url,
                title=title,
                content=content,
                published_at=published_at,
                source=self.source,
            )
        except Exception as e:
            logger.warning(f"解析 Dcard 文章失敗：{e}")
            return None

    def _parse_datetime(self, raw: str) -> str:
        """將 Dcard ISO 8601 日期轉為標準格式。"""
        if not raw:
            return datetime.utcnow().isoformat() + "Z"
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.isoformat().replace("+00:00", "Z")
        except Exception:
            return datetime.utcnow().isoformat() + "Z"
