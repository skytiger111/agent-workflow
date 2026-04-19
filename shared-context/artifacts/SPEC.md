# Market_Sentiment 市場情緒分析工具 — SPEC.md

> **版本：** 1.1
> **更新日期：** 2026-04-19
> **負責 Agent：** analyzer
> **專案：** Market_Sentiment
> **技術棧：** Python（Flask、requests、BeautifulSoup4、sqlite3）、LLM API（Claude / GPT-4o-mini）、HTML/CSS/JS（純前端，Chart.js）

---

## 1. 系統概述

Market_Sentiment 為一個市場情緒分析工具，爬取鉅亨網財經新聞與 PTT/Dcard 股市討論文章，透過 LLM 對每篇文章給予情緒分數（-1 極度悲觀 ~ +1 極度樂觀），將結果持久化至 SQLite，最終由 Flask API + 前端儀表板呈現即時情緒列表與 7 天 / 30 天趨勢圖。

**系統元件：**
- **爬蟲模組**（`crawler/`）：鉅亨網新聞、PTT、Dcard 文章爬取
- **情緒分析模組**（`analyzer/`）：LLM API 整合，情緒分數計算
- **Flask API**（`app.py`）：RESTful API，含文章列表、趨勢查詢、摘要聚合
- **SQLite 資料庫**（`data/market_sentiment.db`）：歷史記錄持久化
- **前端儀表板**（`templates/` + `static/`）：即時情緒卡片列表 + Chart.js 趨勢圖

---

## 2. 功能範圍與 YAGNI 邊界

### 2.1 已納入功能（In Scope）

| 模組 | 功能 |
|------|------|
| 鉅亨網爬蟲 | 爬取首頁頭條新聞標題、連結、摘要、發布時間 |
| PTT 爬蟲（Stock 板） | 爬取 PTT Stock 板文章標題、摘要、發布時間 |
| Dcard 爬蟲（台股討論） | 爬取 Dcard 台股相關文章標題、內文摘要、發布時間 |
| LLM 情緒分析 | 對每篇文章呼叫 LLM，回傳 -1 至 +1 的情緒分數 + 情緒標籤 |
| Flask API | 提供文章列表、情緒趨勢、當日摘要等端點 |
| SQLite 持久化 | 所有爬取文章與分析結果寫入資料庫，含 timestamp |
| 即時情緒卡片列表 | 前端展示最新文章，每張卡片含：標題、來源、情緒分數、情緒標籤 |
| 7 天 / 30 天趨勢圖 | Chart.js 折線圖，X軸日期，Y軸平均情緒分數 |
| 手動觸發爬蟲 | POST `/api/crawl` 可手動重新爬取並分析 |

### 2.2 YAGNI 邊界（Out of Scope）

- 使用者登入與帳號系統
- 即時 WebSocket 推送（目前為輪詢）
- 自動化排程爬蟲（需手動觸發或外部 cron）
- 多語言翻譯
- 多元關鍵字搜尋 / 多股票追蹤（本期聚焦單一股票）
- 輿論龍頭指標（KOL 權重）
- 行動裝置原生 App
- 快取層（Redis / Memcached）
- API 速率限制（Rate Limiting）

---

## 3. 爬蟲模組設計

### 3.1 爬蟲統一介面

所有爬蟲實作同一個抽象基底類別 `BaseCrawler`，確保 API 一致性：

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

### 3.2 爬蟲模組結構

```
crawler/
├── __init__.py
├── base.py          # BaseCrawler 抽象類別
├── cnyes.py         # 鉅亨網爬蟲
├── ptt.py           # PTT Stock 板爬蟲
└── dcard.py         # Dcard 台股版爬蟲
```

### 3.3 鉅亨網爬蟲（`crawler/cnyes.py`）

**目標 URL：** `https://news.cnyes.com/news/category/headline`

**爬取方式：** GET，每頁 20 筆，最多爬 3 頁（60 筆/次）

**解析欄位：**
| 欄位 | 說明 |
|------|------|
| `url` | 新聞文章完整 URL |
| `title` | 新聞標題 |
| `content` | 文章內容（摘要或前500字） |
| `published_at` | 發布時間（ISO 8601） |
| `source` | 固定值 `"cnyes"` |

**反爬策略：**
- `User-Agent` 偽裝
- 每篇文章間隔 1–3 秒隨機延遲
- HTTP 429 時 sleep 30 秒後重試（最多 3 次）

### 3.4 PTT 爬蟲（`crawler/ptt.py`）

**目標 URL：** `https://www.ptt.cc/bbs/Stock/index.html`

**爬取方式：** GET，Cookie 需帶 `over18=1`，從首頁往後爬 2 頁（約 40 筆/次）

**解析欄位：**
| 欄位 | 說明 |
|------|------|
| `url` | PTT 文章完整 URL（含 `https://www.ptt.cc` 前綴） |
| `title` | 文章標題 |
| `content` | 文章內容（純文字，前 1000 字） |
| `published_at` | 發布時間（ISO 8601） |
| `source` | 固定值 `"ptt"` |

**防護：** 同一 IP 短時間大量請求會被阻擋，需控制頻率

### 3.5 Dcard 爬蟲（`crawler/dcard.py`）

**目標 URL：** `https://www.dcard.tw/service/api/v2/posts?forum=stock&limit=30`

**爬取方式：** REST GET，`before` 參數往回取 2 次（約 60 筆/次）

**解析欄位：**
| 欄位 | 說明 |
|------|------|
| `url` | Dcard 文章 URL |
| `title` | 文章標題 |
| `content` | 文章內容（前 500 字） |
| `published_at` | 發布時間（ISO 8601） |
| `source` | 固定值 `"dcard"` |

### 3.6 爬蟲錯誤處理

| 情境 | 處理方式 |
|------|----------|
| HTTP 4xx（客戶端錯誤） | 記錄警告，跳過該請求，不阻斷整體流程 |
| HTTP 5xx（伺服器錯誤） | 重試 2 次，間隔 3 秒，仍失敗則略過 |
| 連線逾時（10秒） | 視為失敗，略過 |
| 無文章（空回應） | 記錄警告，回傳空列表 |
| 解析失敗（JSON/HTML） | 記錄錯誤，回傳空列表 |

---

## 4. LLM 情緒分析 API 設計

### 4.1 分析流程

```
文章（標題 + 內容）
    ↓
Prompt 模板組裝
    ↓
呼叫 LLM API（gpt-4o-mini 或 claude-3-5-haiku）
    ↓
解析 JSON 回應：{ sentiment_score, label, reasoning }
    ↓
寫入 SQLite
```

### 4.2 Prompt 設計

**系統提示詞：**
```
你是一個專業的金融市場情緒分析師。請根據以下文章內容，判斷其對相關股票/市場的情緒影響。
回傳嚴謹、客觀的分析結果。
```

**使用者提示詞：**
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

### 4.3 Request 格式

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

### 4.4 Response 解析

```json
{
  "sentiment_score": 0.72,
  "label": "positive",
  "reasoning": "多數分析師上調目標價，基本面持續看好"
}
```

### 4.5 分數映射規則

| 分數區間 | Label | 顏色（前端） |
|----------|-------|-------------|
| ≥ 0.6 | positive | 綠色 `#22c55e` |
| > -0.3 且 < 0.6 | neutral | 灰色 `#9ca3af` |
| ≤ -0.3 | negative | 紅色 `#ef4444` |

### 4.6 LLM 錯誤處理

| 情境 | 處理方式 |
|------|----------|
| API Key 缺失 | `ValueError` 明確提示需設定金鑰 |
| API 回應非 200 | 記錄錯誤，分數預設為 `0.0`，label 為 `"neutral"` |
| JSON 解析失敗 | 記錄錯誤，分數預設為 `0.0`，label 為 `"neutral"` |
| 速率限制（429） | 重試 1 次，仍失敗則給予預設分數 |

---

## 5. Flask API 端點設計

### 5.1 端點總覽

| 方法 | 路徑 | 說明 |
|------|------|------|
| `GET` | `/api/news` | 最新文章列表（含情緒分數） |
| `GET` | `/api/trend` | 情緒趨勢（支援 7/30 天） |
| `GET` | `/api/summary` | 當日摘要統計 |
| `POST` | `/api/crawl` | 手動觸發爬蟲 |
| `GET` | `/health` | 健康檢查 |

### 5.2 GET /api/news

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

### 5.3 GET /api/trend

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

### 5.4 GET /api/summary

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

### 5.5 POST /api/crawl

**成功回應（202）：**
```json
{
  "code": 202,
  "message": "Crawl started",
  "data": {"crawl_id": "abc123"}
}
```

### 5.6 GET /health

**成功回應（200）：**
```json
{"status": "ok", "db": "connected", "timestamp": "2026-04-19T09:00:00Z"}
```

---

## 6. 前端儀表板佈局與元件

### 6.1 頁面結構

```
index.html（單頁應用）
├── Header（標題 + 最後更新時間 + 刷新按鈕）
├── 摘要卡片區（Summary Cards，3 格）
├── 趨勢圖區（Trend Chart + 7天/30天 切換）
├── 篩選列（來源過濾：全部 / 鉅亨 / PTT / Dcard）
└── 文章列表（即時文章情緒卡片）
```

### 6.2 摘要卡片（Summary Cards，3 格）

| 卡片 | 內容 |
|------|------|
| 今日平均情緒 | 分數（+0.18）+ 標籤（positive/neutral/negative）+ 對應色彩 |
| 今日文章數 | 總計 + 各來源分解 |
| 市場情緒狀態 | 描述文字（「市場情緒偏正面」） |

### 6.3 趨勢圖（Trend Chart）

- **套件：** Chart.js（CDN 引入）
- **類型：** 折線圖（Line Chart）
- **X 軸：** 日期（近 7 天或近 30 天）
- **Y 軸：** 平均情緒分數（-1 ~ 1）
- **參考線：** Y=0（中性基準線，灰虛線）
- **配色：**
  - 正值區域：填滿綠色半透明
  - 負值區域：填滿紅色半透明
- **切換按鈕：** 「7天」/「30天」tab，點擊切換

### 6.4 文章列表（Article List）

每筆顯示：
- **來源標籤**（彩色 Badge：「鉅亨」藍 /「PTT」橙 /「Dcard」紫）
- **文章標題**（超連結，target `_blank`，max 2 行，溢出省略）
- **發布時間**（相對時間：「3 小時前」）
- **情緒分數 + 進度條**（分數視覺化，映射至 0% ~ 100%）
- **情緒標籤**（positive/neutral/negative）
- 支援「載入更多」分頁

### 6.5 分數顏色對應

| 分數區間 | Label | 顏色 |
|----------|-------|------|
| ≥ 0.6 | positive | 綠色 `#22c55e` |
| ≤ -0.3 | negative | 紅色 `#ef4444` |
| 其他 | neutral | 灰色 `#9ca3af` |

### 6.6 響應式斷點

| 斷點 | 佈局變化 |
|------|----------|
| ≤ 768px | Summary Cards 單欄堆疊，Chart 寬度 100% |
| > 768px | Summary Cards 三欄並排，Chart 最大寬度 800px |

### 6.7 前端錯誤處理

- API 請求失敗時顯示「資料載入失敗，請稍後重試」提示
- 空白狀態（尚無資料）顯示引導訊息

---

## 7. 資料庫 Schema（SQLite）

### 7.1 資料庫檔案

- 位置：`{project_root}/data/market_sentiment.db`
- 初始化：Flask 啟動時自動建立 tables（如不存在）

### 7.2 Table: articles

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

### 7.3 Table: crawl_logs

```sql
CREATE TABLE crawl_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT    NOT NULL,
    started_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at     DATETIME,
    article_count   INTEGER DEFAULT 0,
    status          TEXT    DEFAULT 'running' CHECK(status IN ('running', 'success', 'failed'))
);
```

### 7.4 查詢效能考量

- `articles` 表有複合索引支援來源過濾 + 趨勢查詢
- 每次爬蟲前檢查 `url` 是否已存在（UPSERT），避免重複儲存

---

## 8. 異常處理與 HTTP 狀態碼對照表

### 8.1 Flask 錯誤回應格式

所有錯誤回應均使用以下格式：
```json
{
  "code": <HTTP 狀態碼>,
  "message": "<人類可讀錯誤訊息>",
  "data": null
}
```

### 8.2 狀態碼對照

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

## 9. 環境變數

| 變數 | 必填 | 說明 |
|------|------|------|
| `OPENAI_API_KEY` | 建議 | OpenAI API 金鑰（用於情緒分析） |
| `ANTHROPIC_API_KEY` | 備援 | Anthropic API 金鑰 |
| `FLASK_ENV` | 否 | `development`（預設）或 `production` |
| `DATABASE_PATH` | 否 | SQLite 資料庫路徑（預設 `data/market_sentiment.db`） |

---

## 10. 專案目錄結構

```
Market_Sentiment/
├── app.py              # Flask 應用程式入口
├── config.py           # 環境變數讀取
├── database.py          # SQLite 初始化與 CRUD
├── crawler/
│   ├── __init__.py
│   ├── base.py          # BaseCrawler 抽象類別
│   ├── cnyes.py
│   ├── ptt.py
│   └── dcard.py
├── analyzer/
│   ├── __init__.py
│   └── sentiment.py     # LLM 情緒分析呼叫與解析
├── static/
│   ├── style.css
│   └── app.js           # 前端 JS
├── templates/
│   └── index.html       # 儀表板 HTML
├── tests/
│   ├── __init__.py
│   ├── test_crawler.py
│   ├── test_analyzer.py
│   └── test_api.py
├── data/                # SQLite DB 存放目錄（.gitkeep）
├── requirements.txt
├── .env.example
└── README.md
```

---

## 11. 驗收標準（Acceptance Criteria）

- [ ] 爬蟲可成功抓取三個來源的新聞文章（鉅亨、PTT、Dcard）
- [ ] LLM 對每篇文章輸出 -1 ~ 1 的情緒分數
- [ ] `/api/news` 回傳最新文章列表，分頁正常
- [ ] `/api/trend?days=7` 與 `days=30` 回傳正確趨勢資料
- [ ] `/api/summary` 回傳當日摘要
- [ ] 前端儀表板呈現文章列表與趨勢圖
- [ ] 趨勢圖支援 7天 / 30天 切換
- [ ] 分數視覺化：綠 / 灰 / 紅 正確對應
- [ ] SQLite 正確儲存歷史記錄
- [ ] API 錯誤回應符合 HTTP 狀態碼對照表
- [ ] 前端響應式設計（桌面 / 手機）

---

Developed with 🐯 by Skytiger & **Google Deepmind Antigravity Team**
