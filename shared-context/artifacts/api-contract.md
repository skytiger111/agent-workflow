# Market_Sentiment API 合約文件

> **版本：** 1.0
> **建立日期：** 2026-04-19
> **更新日期：** 2026-04-19
> **負責 Agent：** backend-dev
> **專案：** Market_Sentiment
> **實作狀態：** 🔧 實作中

---

## 實作摘要

本合約實作於 `/Users/tigerclaw/code/Market_Sentiment/` 目錄，Python Flask 後端：
- ✅ 爬蟲模組（crawler/）：鉅亨網、PTT、Dcard
- ✅ LLM 情緒分析（analyzer/sentiment.py）
- ✅ Flask REST API（app.py）
- ✅ SQLite 持久化（database.py）

**LLM API Key：** 從環境變數 `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY` 注入。

---

## 1. 爬蟲統一介面

### BaseCrawler 抽象類別

```python
class BaseCrawler(ABC):
    @abstractmethod
    def fetch(self, limit: int = 20) -> List[dict]:
        """回傳文章列表"""

    @property
    @abstractmethod
    def source(self) -> str:
        """回傳來源代碼：'cnyes'、'ptt'、'dcard'"""
```

### Article 統一資料格式

```python
@dataclass
class Article:
    url: str           # 文章完整 URL
    title: str         # 文章標題
    content: str       # 文章內容（前500-1000字）
    published_at: str  # 發布時間（ISO 8601）
    source: str       # 'cnyes' | 'ptt' | 'dcard'
```

---

## 2. LLM 情緒分析

### Request 格式（OpenAI）

```python
requests.post("https://api.openai.com/v1/chat/completions", json={
    "model": "gpt-4o-mini",
    "messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT}
    ],
    "temperature": 0.1,
    "max_tokens": 200
})
```

### System Prompt

```
你是一個專業的金融市場情緒分析師。請根據以下文章內容，判斷其對相關股票/市場的情緒影響。
回傳嚴謹、客觀的分析結果。
```

### User Prompt

```
文章標題：{title}
文章內容：{content}

請分析這篇文章對股票市場的情緒影響，並以以下 JSON 格式回覆：
{
  "sentiment_score": <浮點數，範圍 -1 到 1，
    越接近 1 代表強烈正面，越接近 -1 代表強烈負面>,
  "label": "<字串，positive / neutral / negative>",
  "reasoning": "<字串，50字以內的簡短分析理由>"
}

只回覆 JSON，不要包含其他文字。
```

### Response 解析

```json
{
  "sentiment_score": 0.72,
  "label": "positive",
  "reasoning": "多數分析師上調目標價，基本面持續看好"
}
```

### 分數映射規則

| 分數區間 | Label | 顏色 |
|----------|-------|------|
| ≥ 0.6 | positive | 綠色 `#22c55e` |
| > -0.3 且 < 0.6 | neutral | 灰色 `#9ca3af` |
| ≤ -0.3 | negative | 紅色 `#ef4444` |

---

## 3. Flask API 端點

### 端點總覽

| 方法 | 路徑 | 說明 |
|------|------|------|
| `GET` | `/api/news` | 最新文章列表（含情緒分數） |
| `GET` | `/api/trend` | 情緒趨勢（支援 7/30 天） |
| `GET` | `/api/summary` | 當日摘要統計 |
| `POST` | `/api/crawl` | 手動觸發爬蟲 |
| `GET` | `/health` | 健康檢查 |

---

### GET /api/news

**查詢參數：**

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `source` | string | `all` | 過濾來源：`cnyes`、`ptt`、`dcard`、`all` |
| `limit` | int | `20` | 回傳筆數（上限 100） |
| `offset` | int | `0` | 分頁偏移 |

**成功回應（200）：**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 156,
    "limit": 20,
    "offset": 0,
    "articles": [
      {
        "id": 42,
        "title": "台積電法說會報喜 市場解讀正面",
        "source": "cnyes",
        "url": "https://news.cnyes.com/...",
        "published_at": "2026-04-19T08:30:00Z",
        "sentiment_score": 0.72,
        "label": "positive",
        "reasoning": "法說會優於預期，半導體展望樂觀",
        "crawled_at": "2026-04-19T09:00:00Z"
      }
    ]
  }
}
```

---

### GET /api/trend

**查詢參數：**

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `days` | int | `7` | 統計區間（7 或 30） |

**成功回應（200）：**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "days": 7,
    "trend": [
      {"date": "2026-04-13", "avg_score": 0.31, "count": 18},
      {"date": "2026-04-14", "avg_score": -0.12, "count": 22},
      {"date": "2026-04-15", "avg_score": 0.45, "count": 15},
      {"date": "2026-04-16", "avg_score": 0.08, "count": 20},
      {"date": "2026-04-17", "avg_score": 0.55, "count": 19},
      {"date": "2026-04-18", "avg_score": -0.22, "count": 24},
      {"date": "2026-04-19", "avg_score": 0.18, "count": 8}
    ],
    "overall_avg": 0.175,
    "overall_count": 126
  }
}
```

---

### GET /api/summary

**成功回應（200）：**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "date": "2026-04-19",
    "avg_score": 0.18,
    "positive_count": 5,
    "neutral_count": 2,
    "negative_count": 1,
    "total_count": 8,
    "sources": {
      "cnyes": 3,
      "ptt": 3,
      "dcard": 2
    }
  }
}
```

---

### POST /api/crawl

**成功回應（202）：**
```json
{
  "code": 202,
  "message": "Crawl started",
  "data": {"crawl_id": "abc123"}
}
```

**錯誤回應（429）：** 爬蟲仍在執行中
```json
{
  "code": 429,
  "message": "Crawl already in progress",
  "data": null
}
```

---

### GET /health

**成功回應（200）：**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "status": "ok",
    "db": "connected",
    "timestamp": "2026-04-19T09:00:00Z"
  }
}
```

---

## 4. 錯誤回應格式

所有錯誤回應均使用以下格式：
```json
{
  "code": <HTTP 狀態碼>,
  "message": "<人類可讀錯誤訊息>",
  "data": null
}
```

---

## 5. HTTP 狀態碼對照表

| HTTP 狀態碼 | 情境 | 回應 message |
|------------|------|-------------|
| 200 | 成功（GET） | `"success"` |
| 202 | 爬蟲已啟動 | `"Crawl started"` |
| 400 | 參數錯誤（如 days 非 7/30） | `"Invalid parameter: days must be 7 or 30"` |
| 404 | 找不到資源 | `"Resource not found"` |
| 429 | 爬蟲仍在執行中 | `"Crawl already in progress"` |
| 500 | 資料庫或伺服器錯誤 | `"Internal server error"` |
| 503 | 外部 API（LLM/爬蟲）無法連線 | `"Service unavailable: unable to reach LLM API"` |

---

## 6. 資料庫 Schema

### Table: articles

```sql
CREATE TABLE articles (
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

CREATE INDEX idx_articles_source ON articles(source);
CREATE INDEX idx_articles_published_at ON articles(published_at);
CREATE INDEX idx_articles_crawled_at ON articles(crawled_at);
```

### Table: crawl_logs

```sql
CREATE TABLE crawl_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT    NOT NULL,
    started_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at    DATETIME,
    article_count   INTEGER DEFAULT 0,
    status          TEXT    DEFAULT 'running' CHECK(status IN ('running', 'success', 'failed'))
);
```

---

Developed with 🐯 by 標虎團隊 | 技術總監: 匠 (Coder Agent)
