"""
BaseCrawler 抽象類別 — 所有爬蟲的統一介面。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import List


@dataclass
class Article:
    """統一的文章資料結構。"""
    url: str
    title: str
    content: str
    published_at: str  # ISO 8601
    source: str        # 'cnyes' | 'ptt' | 'dcard'


class BaseCrawler(ABC):
    """爬蟲抽象基底類別。"""

    @property
    @abstractmethod
    def source(self) -> str:
        """回傳來源代碼：'cnyes'、'ptt'、'dcard'。"""
        ...

    @abstractmethod
    def fetch(self, limit: int = 20) -> List[Article]:
        """
        爬取文章，回傳 Article 列表。
        失敗時回傳空列表，不拋出例外。
        """
        ...

    def to_dict(self, article: Article) -> dict:
        """將 Article 轉為字典（供 JSON 序列化）。"""
        return asdict(article)
