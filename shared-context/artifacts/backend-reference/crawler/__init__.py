"""
爬蟲模組工廠 — 依據來源代碼回傳對應爬蟲實例。
"""
from crawler.base import BaseCrawler
from crawler.cnyes import CnyesCrawler
from crawler.ptt import PttCrawler
from crawler.dcard import DcardCrawler


def get_crawler(source: str) -> BaseCrawler:
    """依 source 代碼回傳爬蟲實例。"""
    crawlers = {
        "cnyes": CnyesCrawler,
        "ptt": PttCrawler,
        "dcard": DcardCrawler,
    }
    cls = crawlers.get(source.lower())
    if cls is None:
        raise ValueError(f"未知來源：{source}，支援：{list(crawlers.keys())}")
    return cls()


def get_all_crawlers():
    """回傳所有爬蟲實例列表。"""
    return [CnyesCrawler(), PttCrawler(), DcardCrawler()]
