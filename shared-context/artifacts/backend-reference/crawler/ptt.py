"""
PTT Stock 板爬蟲 — https://www.ptt.cc/bbs/Stock/index.html
"""
import random
import time
import logging
import re
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
    "Cookie": "over18=1",
    "Accept": "text/html",
}


class PttCrawler(BaseCrawler):
    """PTT Stock 板爬蟲。"""

    BASE_URL = "https://www.ptt.cc/bbs/Stock/index.html"

    @property
    def source(self) -> str:
        return "ptt"

    def fetch(self, limit: int = 20) -> List[Article]:
        """從 PTT Stock 板首頁往後爬取 2 頁（約 40 筆）。"""
        articles: List[Article] = []
        pages = min(3, (limit + 19) // 20)

        url = self.BASE_URL

        for _ in range(pages):
            try:
                resp = requests.get(url, headers=HEADERS, timeout=10)
                if resp.status_code != 200:
                    logger.warning(f"PTT HTTP {resp.status_code}，略過")
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                items = soup.select("div.r-ent")

                for item in items:
                    article = self._parse_item(item)
                    if article:
                        articles.append(article)
                        if len(articles) >= limit:
                            return articles[:limit]

                # 取得上一頁連結
                prev_link = soup.select_one("a.btn.wide:last-of-type")
                if prev_link and prev_link.get("href"):
                    url = "https://www.ptt.cc" + prev_link["href"]
                else:
                    break

                # 反爬延遲
                time.sleep(random.uniform(1, 3))

            except requests.Timeout:
                logger.warning("PTT 連線逾時，略過")
                break
            except Exception as e:
                logger.error(f"PTT 爬蟲錯誤：{e}")
                break

        return articles[:limit]

    def _parse_item(self, item) -> Article | None:
        """解析單筆 PTT 文章。"""
        try:
            # 標題
            title_tag = item.select_one("div.title a")
            if not title_tag:
                return None
            title = title_tag.get_text(strip=True)
            if not title or title.startswith("[公告]"):
                return None

            # URL
            url = title_tag.get("href", "")
            if not url.startswith("http"):
                url = f"https://www.ptt.cc{url}"

            # 作者與時間
            meta = item.select("div.meta")
            author = meta[0].get_text(strip=True) if meta else ""
            date_str = ""
            for m in meta:
                text = m.get_text(strip=True)
                # 格式：MM/DD 或 YYYY/MM/DD
                if re.match(r"\d{2}/\d{2}", text) or re.match(r"\d{4}/\d{2}/\d{2}", text):
                    date_str = text
                    break

            published_at = self._parse_date(date_str)

            # 摘要（取 POPULAR 或-meta 部分）
            content = item.select_one("div.push-content")
            content = content.get_text(strip=True) if content else title

            return Article(
                url=url,
                title=title,
                content=content[:1000],
                published_at=published_at,
                source=self.source,
            )
        except Exception as e:
            logger.warning(f"解析 PTT 文章失敗：{e}")
            return None

    def _parse_date(self, raw: str) -> str:
        """將 PTT 日期格式轉為 ISO 8601。"""
        if not raw:
            return datetime.utcnow().isoformat() + "Z"
        try:
            # 格式可能是 MM/DD 或 YYYY/MM/DD
            if len(raw) <= 5:
                year = datetime.now().year
                dt = datetime.strptime(f"{year}/{raw}", "%Y/%m/%d")
            else:
                dt = datetime.strptime(raw, "%Y/%m/%d")
            return dt.isoformat() + "Z"
        except Exception:
            return datetime.utcnow().isoformat() + "Z"
