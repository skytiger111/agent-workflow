# Market Sentiment API 合約文件

> 本文件記錄 Market Sentiment 後端 API 的完整合約，包含端點規格、請求/回應格式與錯誤處理。
> 基礎 URL：`http://<host>:5000/api`

---

## 目錄

- [1. 健康檢查](#1-健康檢查)
- [2. 觸發爬蟲](#2-觸發爬蟲)
- [3. 文章列表](#3-文章列表)
- [4. 趨勢資料](#4-趨勢資料)
- [5. 最新情緒分數](#5-最新情緒分數)
- [6. 情緒歷史](#6-情緒歷史)
- [7. 當日摘要](#7-當日摘要)
- [8. 錯誤回應格式](#8-錯誤回應格式)

---

## 1. 健康檢查

### `GET /api/health`

確認服務運作正常。

**Response 200**

```json
{
  "status": "ok",
  "timestamp": "2026-04-19T07:30:00.000000"
}
```

| 欄位       | 類型   | 說明                   |
|------------|--------|------------------------|
| `status`   | string | 固定值 `"ok"`          |
| `timestamp`| string | UTC ISO 8601 時間戳   |

---

## 2. 觸發爬蟲

### `POST /api/crawl`

依指定來源執行爬蟲，並對文章進行 LLM 情緒分析。為非同步執行（立即回傳 202）。

**Request Body**（可選）

```json
{
  "sources": ["cnyes", "ptt", "dcard"]
}
```

| 欄位      | 類型     | 預設值                           | 說明                              |
|-----------|----------|----------------------------------|-----------------------------------|
| `sources` | string[] | `["cnyes", "ptt", "dcard"]`     | 要爬取的來源陣列                  |

**Response 202（Accepted）**

```json
{
  "status": "ok",
  "fetched": {
    "cnyes": 15,
    "ptt": 20,
    "dcard": 10
  },
  "analyzed": 45
}
```

| 欄位       | 類型   | 說明                                       |
|------------|--------|--------------------------------------------|
| `status`   | string | 固定值 `"ok"`                             |
| `fetched`  | object | 各來源實際爬取的文章數量                   |
| `analyzed` | int    | 成功完成 LLM 情緒分析的文章數量（所有來源加總） |

**Response 500（Internal Error）**

LLM API 完全無法呼叫時，整體仍回 202（爬蟲成功），但 `analyzed` 為 0。
若資料庫寫入失敗則回 500。

---

## 3. 文章列表

### `GET /api/articles`

取得已儲存的文章列表（含情緒分數）。

**Query Parameters**

| 參數    | 類型    | 預設值 | 說明                         |
|---------|---------|--------|------------------------------|
| `limit` | integer | 50     | 回傳文章數量上限（最大 200） |
| `source`| string  | null   | 依來源過濾：`cnyes` / `ptt` / `dcard` |

**Response 200**

```json
{
  "articles": [
    {
      "id": 1,
      "external_id": "cnyes-123456",
      "title": "台股大漲 200 點！半導體族群全面噴出",
      "url": "https://news.cnyes.com/news/id/123456",
      "source": "cnyes",
      "published_at": "2026-04-19T08:30:00",
      "push_count": 0,
      "likes": 0,
      "raw_text": "台股今（19）日錶...",
      "sentiment_score": 0.72,
      "sentiment_reason": "半導體需求回升，利多信號明顯",
      "created_at": "2026-04-19T08:31:00"
    }
  ]
}
```

**articles 欄位說明**

| 欄位               | 類型     | 說明                                              |
|--------------------|----------|---------------------------------------------------|
| `id`               | integer  | 資料庫主鍵                                        |
| `external_id`      | string   | 外部來源 ID（格式：`{source}-{hash}`）            |
| `title`            | string   | 文章標題                                          |
| `url`              | string   | 文章連結                                          |
| `source`           | string   | 來源：`cnyes` / `ptt` / `dcard`                   |
| `published_at`     | string   | 發布時間 ISO 8601                                 |
| `push_count`       | integer  | PTT 推文數（PTT 文章適用）                        |
| `likes`            | integer  | Dcard 喜歡數（Dcard 文章適用）                    |
| `raw_text`         | string   | 供 LLM 分析用之原始文字                           |
| `sentiment_score`  | float    | 情緒分數（-1.0 ~ +1.0），尚未分析時為 `null`     |
| `sentiment_reason` | string   | 分數原因說明                                      |
| `created_at`       | string   | 寫入資料庫時間                                    |

---

## 4. 趨勢資料

### `GET /api/trend`

取得指定天期的情緒趨勢資料（時別彙總）。

**Query Parameters**

| 參數   | 類型   | 預設值 | 說明                              |
|--------|--------|--------|-----------------------------------|
| `range`| string | `7d`   | 時間範圍：`7d`（7天）或 `30d`（30天）|

**Response 200**

```json
{
  "range": "7d",
  "points": [
    {
      "hour_key": "2026-04-19-08",
      "avg_score": 0.42,
      "article_count": 12
    },
    {
      "hour_key": "2026-04-19-09",
      "avg_score": 0.38,
      "article_count": 15
    }
  ]
}
```

**points 欄位說明**

| 欄位           | 類型    | 說明                                         |
|----------------|---------|----------------------------------------------|
| `hour_key`     | string  | 小時鍵（格式：`YYYY-MM-DD-HH`）              |
| `avg_score`    | float   | 該小時所有文章情緒分數的平均值                |
| `article_count`| integer | 該小時分析的文章數量                          |

**Response 400**

```json
{
  "error": "無效的 range 參數，請使用 7d 或 30d"
}
```

---

## 5. 最新情緒分數

### `GET /api/sentiment-score`

取得最近 1 小時內的最新市場情緒平均分數。

**Response 200（有資料）**

```json
{
  "score": 0.4521
}
```

**Response 200（尚無資料）**

```json
{
  "score": null,
  "message": "尚無情緒分數資料"
}
```

---

## 6. 情緒歷史

### `GET /api/sentiment-history`

取得過去指定天數的情緒歷史分數。

**Query Parameters**

| 參數  | 類型    | 預設值 | 說明                          |
|-------|---------|--------|-------------------------------|
| `days`| integer | 7      | 回顧天數（最大 90）            |

**Response 200**

```json
{
  "points": [
    {
      "hour_key": "2026-04-18-10",
      "avg_score": 0.55,
      "article_count": 8
    }
  ]
}
```

---

## 7. 當日摘要

### `GET /api/summary`

取得當日情緒摘要統計。

**Response 200**

```json
{
  "date": "2026-04-19",
  "article_count": 47,
  "avg_score": 0.3125,
  "min_score": -0.45,
  "max_score": 0.88
}
```

| 欄位          | 類型   | 說明                         |
|---------------|--------|------------------------------|
| `date`        | string | 查詢日期（YYYY-MM-DD）       |
| `article_count`| int   | 當日已分析文章數             |
| `avg_score`   | float  | 當日平均分數                 |
| `min_score`   | float  | 當日最低分數                 |
| `max_score`   | float  | 當日最高分數                 |

---

## 8. 錯誤回應格式

所有錯誤回應均包含 `error` 欄位：

```json
{
  "error": "<錯誤訊息>"
}
```

### HTTP 狀態碼對照

| 情境             | HTTP 狀態        | `error` 內容                                   |
|------------------|------------------|------------------------------------------------|
| 參數驗證失敗      | 400              | `無效的 range 參數，請使用 7d 或 30d`           |
| 找不到端點        | 404              | `找不到指定端點` / `找不到指定資源`             |
| 爬蟲完成（async）| 202              | —（不回錯誤，正常回應）                         |
| 資料庫錯誤        | 500              | `伺服器內部錯誤` 或具體 Exception 訊息          |
| 全域未處理例外    | 500              | Exception 訊息內容                              |

> **備註**：爬蟲為非同步執行，API 端點收到 202 即表示已成功接收請求並啟動執行，不保證此時已完成。

---

Developed with 🐯 by Skytiger & **Google Deepmind Antigravity Team**
