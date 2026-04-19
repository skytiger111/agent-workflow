# API 合約文件 — MiniMax Multi-Media Server

> **版本：** 1.0
> **建立日期：** 2026-04-17
> **更新日期：** 2026-04-17
> **負責 Agent：** backend-dev
> **專案：** minimax-image-server
> **實作狀態：** ✅ 已實作（2026-04-17）

---

## 實作摘要

本合約實作於 `{project_root}/src/index.ts`，Express + TypeScript 單一入口檔案：
- ✅ MiniMax image-01 圖片生成 (`/api/generate`)
- ✅ MiniMax image-01 圖片編輯 (`/api/image2image`) 含 multer 上傳處理
- ✅ MiniMax speech-2.8-hd 文字轉語音 (`/api/tts`)
- ✅ MiniMax music-2.5 音樂生成 (`/api/music`)
- ✅ MiniMax Hailuo-2.3 影片生成 (`/api/video`) 含任務輪詢 (`/api/video/:task_id`)
- ✅ Session 歷史紀錄（記憶體 Map）
- ✅ 完整錯誤處理（400/401/403/404/413/415/422/429/500/502/503）
- ✅ 健康檢查端點 (`/health`)
- ✅ 嵌入式 HTML UI (`const UI`)

**MiniMax API Key：** 從環境變數 `MINIMAX_API_KEY` 注入，嚴禁寫入程式碼。

---

## 1. 圖片生成

### `POST /api/generate`

文字 Prompt 生成圖片（Mono-理解 MiniMax image-01）。

**Request：**
```json
{
  "prompt": "一隻在森林中奔跑的可愛老虎",
  "aspect_ratio": "1:1",
  "resolution": "1024x1024"
}
```

| 欄位 | 型別 | 必填 | 預設 | 說明 |
|------|------|------|------|------|
| prompt | string | ✅ | — | 生成提示詞（≤2000 字） |
| aspect_ratio | string | ❌ | `1:1` | 寬高比：`1:1` / `16:9` / `9:16` / `4:3` |
| resolution | string | ❌ | `1024x1024` | 解析度 |

**Response `200`：**
```json
{
  "success": true,
  "task_id": "img_abc123",
  "image_url": "https://cdn.minimax.io/...",
  "prompt": "一隻在森林中奔跑的可愛老虎",
  "created_at": "2026-04-17T12:00:00Z"
}
```

**異常 `400`** — Prompt 為空或長度超限
```json
{ "error": "Prompt 不能為空" }
```

**異常 `401`** — 未設定 MINIMAX_API_KEY
```json
{ "error": "MINIMAX_API_KEY 未設定" }
```

**異常 `500`** — MiniMax API 呼叫失敗
```json
{ "error": "圖片生成失敗，請稍後再試" }
```

---

## 2. 圖片編輯

### `POST /api/image2image`

參考圖上傳 + Prompt → 風格編輯（Mono-理解 MiniMax image-01 i2i 模式）。

**Request：** `multipart/form-data`

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| image | File | ✅ | 參考圖（PNG/JPG/WebP，最大 10MB） |
| prompt | string | ✅ | 修改提示詞 |
| strength | number | ❌ | 風格強度 0.0–1.0（預設 0.7） |

**Response `200`：**
```json
{
  "success": true,
  "task_id": "i2i_xyz789",
  "image_url": "https://cdn.minimax.io/...",
  "original_filename": "upload_abc123.png",
  "created_at": "2026-04-17T12:01:00Z"
}
```

**異常 `400`** — 未上傳圖片或 Prompt 為空
```json
{ "error": "必須上傳參考圖片" }
```

**異常 `413`** — 檔案超過 10MB
```json
{ "error": "圖片大小不可超過 10MB" }
```

**異常 `415`** — 不支援格式
```json
{ "error": "僅支援 PNG、JPG、WebP 格式" }
```

---

## 3. 文字轉語音

### `POST /api/tts`

文字 → MiniMax speech-2.8-hd 高清晰度語音合成。

**Request：**
```json
{
  "text": "歡迎使用 MiniMax 多媒體服務，今天天氣真不錯！",
  "voice": "female_young",
  "speed": 1.0,
  "pitch": 0
}
```

| 欄位 | 型別 | 必填 | 預設 | 說明 |
|------|------|------|------|------|
| text | string | ✅ | — | 文字內容（≤1000 字） |
| voice | string | ❌ | `female_young` | 聲音角色 |
| speed | number | ❌ | 1.0 | 速度 0.5–2.0 |
| pitch | number | ❌ | 0 | 音調 -10 至 10 |

**Response `200`：**
```json
{
  "success": true,
  "task_id": "tts_def456",
  "audio_url": "https://cdn.minimax.io/...",
  "duration_seconds": 5.2,
  "text": "歡迎使用 MiniMax...",
  "created_at": "2026-04-17T12:02:00Z"
}
```

**異常 `400`** — Text 為空或長度超限
```json
{ "error": "文字內容不能為空" }
```

---

## 4. 音樂生成

### `POST /api/music`

文字描述 → MiniMax music-2.5 生成音樂。

**Request：**
```json
{
  "prompt": "輕快的夏日流行音樂，BPM 120，有鋼琴和吉他",
  "duration": 30,
  "title": "夏日晴天"
}
```

| 欄位 | 型別 | 必填 | 預設 | 說明 |
|------|------|------|------|------|
| prompt | string | ✅ | — | 音樂描述 |
| duration | number | ❌ | 30 | 時長（秒，最大 300） |
| title | string | ❌ | — | 音樂標題 |

**Response `200`：**
```json
{
  "success": true,
  "task_id": "music_ghi101",
  "audio_url": "https://cdn.minimax.io/...",
  "duration_seconds": 30,
  "title": "夏日晴天",
  "created_at": "2026-04-17T12:03:00Z"
}
```

**異常 `400`** — Prompt 為空
```json
{ "error": "音樂描述不能為空" }
```

---

## 5. 影片生成

### `POST /api/video`

文字或圖片 → MiniMax Hailuo-2.3 生成影片。

**Request（文字模式）：**
```json
{
  "prompt": "一隻可愛的貓在沙發上打哈欠",
  "duration": 5,
  "resolution": "720p"
}
```

**Request（圖片模式）：**
```json
{
  "image_url": "https://example.com/cat.png",
  "prompt": "貓緩慢地眨眼睛",
  "duration": 5
}
```

| 欄位 | 型別 | 必填 | 預設 | 說明 |
|------|------|------|------|------|
| prompt | string | △ | — | 影片描述（文字模式必填） |
| image_url | string | △ | — | 參考圖 URL（圖片模式必填） |
| duration | number | ❌ | 5 | 秒數（最大 30） |
| resolution | string | ❌ | `720p` | 解析度 `720p` / `1080p` |

△ 兩者至少填一，image_url 優先

**Response `200`（同步完成）：**
```json
{
  "success": true,
  "task_id": "vid_jkl202",
  "video_url": "https://cdn.minimax.io/...",
  "status": "completed",
  "duration_seconds": 5,
  "created_at": "2026-04-17T12:04:00Z"
}
```

**Response `200`（非同步，任務建立）：**
```json
{
  "success": true,
  "task_id": "vid_jkl202",
  "status": "pending",
  "message": "影片生成中，請使用 /api/video/:task_id 查詢進度"
}
```

---

### `GET /api/video/:task_id`

查詢影片任務進度。

**Response `200`：**
```json
{
  "task_id": "vid_jkl202",
  "status": "completed",
  "video_url": "https://cdn.minimax.io/...",
  "progress_percent": 100
}
```

**Status 值：** `pending` | `processing` | `completed` | `failed`

**異常 `404`** — 任務 ID 不存在
```json
{ "error": "找不到指定的任務" }
```

---

## 6. 歷史與工具

### `GET /api/history`

取得當前 Session 生成歷史（記憶體 Map 儲存）。

**Response `200`：**
```json
{
  "items": [
    {
      "task_id": "img_abc123",
      "type": "image",
      "prompt": "一隻在森林中奔跑的可愛老虎",
      "result_url": "https://cdn.minimax.io/...",
      "created_at": "2026-04-17T12:00:00Z"
    }
  ],
  "total": 1
}
```

---

### `GET /`

回傳嵌入式 HTML UI（`const UI` 變數）。

---

### `GET /health`

健康檢查端點。

**Response `200`：**
```json
{
  "status": "ok",
  "version": "1.0",
  "uptime_seconds": 3600
}
```

---

## 7. HTTP 狀態碼對照表

| HTTP 狀態碼 | 情境 |
|-------------|------|
| `200` | 成功讀取或任務建立（同步完成） |
| `201` | 非同步任務建立成功（需後續輪詢） |
| `400` | 請求參數錯誤（Prompt 為空、格式不符、長度超限） |
| `401` | 未設定 MINIMAX_API_KEY |
| `403` | API Key 無效或額度不足 |
| `404` | 資源不存在（影片任務 ID 找不到） |
| `409` | 資源衝突 |
| `413` | 圖片上傳超過 10MB |
| `415` | 不支援的媒體格式（PNG/JPG/WebP 以外的圖片） |
| `422` | MiniMax API 業務邏輯錯誤（如 Prompt 含敏感詞） |
| `429` | API 呼叫頻率超限 |
| `500` | 伺服器內部錯誤（網路問題、MiniMax API 故障） |
| `502` | MiniMax API Gateway 錯誤 |
| `503` | MiniMax 服務暫時不可用 |

---

## 8. 錯誤回應格式

```json
{
  "error": "錯誤描述訊息",
  "code": "ERROR_CODE",
  "details": {}
}
```

---

## 9. MiniMax API 型號對照

| 功能 | API 型號 | MiniMax API 端點 |
|------|----------|-----------------|
| 圖片生成 | image-01 | `POST /v1/image generation` |
| 圖片編輯 | image-01 (i2i) | `POST /v1/image generation` |
| 文字轉語音 | speech-2.8-hd | `POST /v1/t2a_v2` |
| 音樂生成 | music-2.5 | `POST /v1/music_generation` |
| 影片生成 | Hailuo-2.3 | `POST /v1/video_generation` |

---

Developed with 🐯 by 標虎團隊 | 技術總監: 匠 (Coder Agent)
