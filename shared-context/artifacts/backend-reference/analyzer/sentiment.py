"""
LLM 情緒分析 — 對文章標題+內容打分數（-1 ~ 1）。
優先使用 OpenAI gpt-4o-mini，失敗時降級至 Anthropic claude-3-5-haiku。
"""
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Prompt 模板
SYSTEM_PROMPT = (
    "你是一個專業的金融市場情緒分析師。"
    "請根據以下文章內容，判斷其對相關股票/市場的情緒影響。"
    "回傳嚴謹、客觀的分析結果。"
)

USER_PROMPT_TEMPLATE = """文章標題：{title}
文章內容：{content}

請分析這篇文章對股票市場的情緒影響，並以以下 JSON 格式回覆：
{{
  "sentiment_score": <浮點數，範圍 -1 到 1，
    越接近 1 代表強烈正面，越接近 -1 代表強烈負面>,
  "label": "<字串，positive / neutral / negative>",
  "reasoning": "<字串，50字以內的簡短分析理由>"
}}

只回覆 JSON，不要包含其他文字。"""


@dataclass
class SentimentResult:
    """情緒分析結果。"""
    sentiment_score: float   # -1 ~ 1
    label: str               # positive / neutral / negative
    reasoning: str           # 分析理由


class SentimentAnalyzer:
    """
    LLM 情緒分析器。
    優先使用 OPENAI_API_KEY，降級使用 ANTHROPIC_API_KEY。
    """

    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not self.openai_key and not self.anthropic_key:
            raise ValueError(
                "必須設定 OPENAI_API_KEY 或 ANTHROPIC_API_KEY 環境變數"
            )

    def analyze(self, title: str, content: str) -> SentimentResult:
        """
        對單篇文章進行情緒分析。
        失敗時回傳預設 neutral 結果。
        """
        if not title and not content:
            return SentimentResult(0.0, "neutral", "空內容")

        # 優先使用 OpenAI
        if self.openai_key:
            result = self._analyze_openai(title, content)
            if result is not None:
                return result

        # 降級至 Anthropic
        if self.anthropic_key:
            result = self._analyze_anthropic(title, content)
            if result is not None:
                return result

        logger.error("所有 LLM API 均失敗，回傳預設 neutral")
        return SentimentResult(0.0, "neutral", "LLM API 不可用")

    def _analyze_openai(self, title: str, content: str) -> Optional[SentimentResult]:
        """使用 OpenAI gpt-4o-mini 分析。"""
        try:
            user_prompt = USER_PROMPT_TEMPLATE.format(
                title=title[:200],
                content=content[:500],
            )
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 200,
                },
                timeout=30,
            )
            if resp.status_code == 429:
                logger.warning("OpenAI 429，等待 30 秒重試")
                time.sleep(30)
                resp = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openai_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 200,
                    },
                    timeout=30,
                )
            if resp.status_code != 200:
                logger.error(f"OpenAI API 錯誤：{resp.status_code} {resp.text[:200]}")
                return None

            raw = resp.json()
            text = raw["choices"][0]["message"]["content"]
            return self._parse_response(text)

        except Exception as e:
            logger.error(f"OpenAI 分析失敗：{e}")
            return None

    def _analyze_anthropic(self, title: str, content: str) -> Optional[SentimentResult]:
        """使用 Anthropic claude-3-5-haiku 分析。"""
        try:
            user_prompt = USER_PROMPT_TEMPLATE.format(
                title=title[:200],
                content=content[:500],
            )
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-3-5-haiku-20241007",
                    "max_tokens": 200,
                    "temperature": 0.1,
                    "system": SYSTEM_PROMPT,
                    "messages": [
                        {"role": "user", "content": user_prompt}
                    ],
                },
                timeout=30,
            )
            if resp.status_code == 429:
                logger.warning("Anthropic 429，等待 30 秒重試")
                time.sleep(30)
                resp = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.anthropic_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "claude-3-5-haiku-20241007",
                        "max_tokens": 200,
                        "temperature": 0.1,
                        "system": SYSTEM_PROMPT,
                        "messages": [
                            {"role": "user", "content": user_prompt}
                        ],
                    },
                    timeout=30,
                )
            if resp.status_code != 200:
                logger.error(f"Anthropic API 錯誤：{resp.status_code} {resp.text[:200]}")
                return None

            raw = resp.json()
            text = raw["content"][0]["text"]
            return self._parse_response(text)

        except Exception as e:
            logger.error(f"Anthropic 分析失敗：{e}")
            return None

    def _parse_response(self, text: str) -> Optional[SentimentResult]:
        """從 LLM 回覆文字解析 JSON。"""
        try:
            # 嘗試取出 ```json ... ``` 或純 JSON
            text = text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            text = text.strip("`").strip()

            data = json.loads(text)
            score = float(data.get("sentiment_score", 0.0))
            # clamp 至 [-1, 1]
            score = max(-1.0, min(1.0, score))
            label = data.get("label", "neutral")
            reasoning = data.get("reasoning", "")[:100]

            return SentimentResult(score, label, reasoning)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失敗：{e}，原始回覆：{text[:200]}")
            return None


# ── 模組層級便利函式 ────────────────────────────────────────────

_analyzer: Optional[SentimentAnalyzer] = None


def get_analyzer() -> SentimentAnalyzer:
    """取得（並快取）全域 SentimentAnalyzer 實例。"""
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentAnalyzer()
    return _analyzer


def analyze_article(title: str, content: str) -> SentimentResult:
    """對文章進行情緒分析（使用全域分析器）。"""
    return get_analyzer().analyze(title, content)
