# MiniMax Multi-Media Server — SPEC.md

> **版本：** 1.1
> **建立日期：** 2026-04-17
> **更新日期：** 2026-04-17
> **負責 Agent：** analyzer
> **專案：** minimax-image-server
> **本版重點：** YT 封面生成功能（YouTube 縮圖）
> **技術棧：** Express + TypeScript（內嵌 HTML UI）、sharp、jimp、MiniMax API

---

## 1. 系統概述

MiniMax 多媒體 API 伺服器（MiniMax Image Server）為一個 Express + TypeScript 網頁服務，透過內嵌 HTML UI 提供圖片生成、圖片編輯、文字轉語音、音樂生成、影片生成，以及 **YouTube 封面（縮圖）生成**六大功能。MiniMax API 金鑰透過環境變數 `MINIMAX_API_KEY` 注入。

**主要元件：**
- **HTTP Server**：Express（`src/index.ts` 為主入口）
- **UI 層**：HTML/CSS/JS 直接內嵌於 Express 回應（`const UI = \`...\``）
- **影像處理**：sharp（高品質處理）、jimp（Node 原生）
- **外部 API**：MiniMax image-01、speech-2.8-hd、music-2.5、Hailuo-2.3

---

## 2. 功能範圍與 YAGNI 邊界

### 2.1 已納入功能（In Scope）

| 模組 | 功能 |
|------|------|
| 圖片生成（Text-to-Image） | 文字 Prompt → MiniMax image-01 生成圖片 |
| **YT 封面生成** | **YouTube 縮圖專用生成：16:9 (1280×720)、文字疊加預覽、標題文字一鍵應用** |
| 圖片編輯（Image-to-Image） | 參考圖上傳 + Prompt → 圖片風格/內容編輯 |
| 文字轉語音（TTS） | 文字 → MiniMax speech-2.8-hd 生成語音 |
| 音樂生成 | 文字描述 → MiniMax music-2.5 生成音樂 |
| 影片生成 | 文字/圖片 Prompt → MiniMax Hailuo-2.3 生成影片 |
| 進度追蹤（影片） | 影片任務 ID → 輪詢查詢完成狀態 |
| 圖片下載 | 生成的圖片/音樂/影片支援直接下載 |
| 歷史紀錄 | 同一 Session 內保留最近生成結果 |
| UI 分頁 | 各功能獨立 Tab 頁面，統一操作體驗 |

### 2.2 YAGNI 邊界（Out of Scope）

- 使用者登入與帳號系統
- 任務佇列與背景處理（目前為同步/輪詢）
- 歷史紀錄持久化（Session 暫存，重啟後清除）
- 多人協作/即時同步
- 自訂模型參數（目前使用 MiniMax 預設）
- 圖片壓縮/格式轉換上傳端（仅處理生成結果）
- API Key 管理介面（金鑰由環境變數注入）
- 費用/用量統計儀表板
- YouTube API 直接發布整合（僅生成縮圖，不上傳）

---

## 3. API 端點

### 3.1 圖片生成

#### `POST /api/generate`

文字 Prompt 生成圖片。

**Request：**
```json
{
  "prompt": "一隻在森林中奔跑的可愛老虎",
  "aspect_ratio": "1:1",
  "resolution": "1024x1024"
}
```

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| prompt | string | ✅ | 生成提示詞（中文/英文皆可） |
| aspect_ratio | string | ❌ | 寬高比（預設 `1:1`），可用 `16:9`、`9:16`、`4:3` |
| resolution | string | ❌ | 解析度（預設 `1024x1024`） |

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

**異常 `400`** — Prompt 為空或長度超限（建議 ≤ 2000 字）
```json
{ "error": "Prompt 不能為空" }
```

**異常 `500`** — MiniMax API 呼叫失敗
```json
{ "error": "圖片生成失敗，請稍後再試" }
```

---

#### `POST /api/image2image`

圖片 + Prompt 進行風格編輯。

**Request（multipart/form-data）：**
| 欄位 | 類型 | 說明 |
|------|------|------|
| image | File | 參考圖片（支援 PNG/JPG/WebP，最大 10MB） |
| prompt | string | 修改提示詞 |
| strength | number | 風格強度 0.0–1.0（預設 0.7） |

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

**異常 `413`** — 檔案過大
```json
{ "error": "圖片大小不可超過 10MB" }
```

**異常 `415`** — 不支援的檔案格式
```json
{ "error": "僅支援 PNG、JPG、WebP 格式" }
```

---

### 3.2 YT 封面生成

#### `POST /api/yt-thumbnail`

YouTube 縮圖專用生成端點，固定 1280×720（16:9）尺寸，支援**自由拖曳調整文字位置**。

**Request：**
```json
{
  "prompt": "科技產品評測影片封面，暗色背景",
  "titleText": "iPhone 16 評測",
  "titleFontSize": 72,
  "titleColor": "#FFFFFF",
  "titlePosition": { "x": 0.5, "y": 0.85 },
  "subtitleText": "完整評測搶先看",
  "subtitleFontSize": 36,
  "subtitleColor": "#FFD700",
  "subtitlePosition": { "x": 0.5, "y": 0.93 },
  "textShadow": true,
  "style": "cinematic",
  "backgroundId": "bg-dark",
  "format": "jpg"
}
```

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| prompt | string | ✅ | 縮圖主體描述（背景、場景） |
| titleText | string | ❌ | 主標題文字（最多 80 字） |
| titleFontSize | number | ❌ | 主標題字體大小 24–120 px（預設 72） |
| titleColor | string | ❌ | 主標題顏色，十六進位（預設 `#FFFFFF`） |
| titlePosition | object | ❌ | **主標題位置 `{ x, y }`，比例 0.0–1.0**（預設 `{ x: 0.5, y: 0.85 }`） |
| subtitleText | string | ❌ | 副標題文字（最多 120 字，可為空字串則不渲染） |
| subtitleFontSize | number | ❌ | 副標題字體大小（預設 36） |
| subtitleColor | string | ❌ | 副標題顏色（預設 `#FFFFFF`） |
| subtitlePosition | object | ❌ | **副標題位置 `{ x, y }`，比例 0.0–1.0**（預設 `{ x: 0.5, y: 0.93 }`） |
| textShadow | boolean | ❌ | 是否啟用文字陰影（預設 `true`） |
| style | string | ❌ | 風格預設：`cinematic`、`vibrant`、`minimal`、`dramatic`（預設 `cinematic`） |
| backgroundId | string | ❌ | 背景圖 ID（可選，若留空則以 prompt 生成 AI 背景） |
| format | string | ❌ | 輸出格式：`jpg`（預設）/ `png` |

**Position 說明**：`{ x: 0.5, y: 0.5 }` = 圖片正中央，`{ x: 0.0, y: 0.0 }` = 左上角，`{ x: 1.0, y: 1.0 }` = 右下角。

**Response `200`：**
```json
{
  "success": true,
  "task_id": "yt_abc123",
  "imageUrl": "/output/yt-cover-{timestamp}.jpg",
  "resolution": "1280x720",
  "format": "jpg",
  "prompt": "科技產品評測影片封面...",
  "titleText": "iPhone 16 評測",
  "createdAt": "2026-04-18T00:00:00Z"
}
```

**異常 `400`** — Prompt 為空或 titleText 超過 80 字
```json
{ "success": false, "error": { "code": "VALIDATION_ERROR", "message": "Prompt 不能為空", "fields": ["prompt"] } }
```

**異常 `400`** — style 或 format 非有效值
```json
{ "success": false, "error": { "code": "VALIDATION_ERROR", "message": "不支援的 style，請使用 cinematic / vibrant / minimal / dramatic" } }
```

**異常 `422`** — 背景圖讀取失敗
```json
{ "success": false, "error": { "code": "BACKGROUND_NOT_FOUND", "message": "找不到指定的背景圖" } }
```

**異常 `500`** — MiniMax API 呼叫失敗
```json
{ "success": false, "error": { "code": "INTERNAL_ERROR", "message": "YT 封面生成失敗，請稍後再試" } }
```

**實作邏輯：**
1. 後端將 `style` 轉譯為 prompt 前綴（如 `cinematic` → `Cinematic lighting, film grain, `）
2. 若有 `backgroundId`，讀取本地背景圖；否則呼叫 MiniMax image-01 生成背景（固定 1280×720）
3. 將 `titlePosition` / `subtitlePosition`（比例）轉換為絕對像素座標
4. 使用 sharp 在圖片上疊加主標題文字圖層（SVG → PNG → composite）
5. 若有 `subtitleText`，再疊加副標題文字圖層
6. 輸出至 `/output/yt-cover-{timestamp}.{format}`，回傳 URL

---

#### `POST /api/yt-thumbnail/preview`

即时預覽端點，**不上傳至 CDN**，回傳 base64 data URI，用於拖曳時即时更新 UI（debounce 300ms）。

**Request Body**：同 `/api/yt-thumbnail`（唯 `format` 固定為 `jpg`，`quality` 固定為 80）

**Response `200`：**
```json
{
  "success": true,
  "dataUri": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
}
```

**異常 `400`**：`{ "success": false, "error": { "code": "VALIDATION_ERROR", "message": "..." } }`
**異常 `500`**：`{ "success": false, "error": { "code": "INTERNAL_ERROR", "message": "..." } }`

---

### 3.3 文字轉語音

#### `POST /api/tts`

文字轉語音。

**Request：**
```json
{
  "text": "歡迎使用 MiniMax 多媒體服務，今天天氣真不錯！",
  "voice": "female_young",
  "speed": 1.0,
  "pitch": 0
}
```

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| text | string | ✅ | 要轉換的文字（建議 ≤ 1000 字） |
| voice | string | ❌ | 聲音角色（預設 `female_young`） |
| speed | number | ❌ | 速度 0.5–2.0（預設 1.0） |
| pitch | number | ❌ | 音調 -10 至 10（預設 0） |

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

### 3.4 音樂生成

#### `POST /api/music`

文字描述生成音樂。

**Request：**
```json
{
  "prompt": "輕快的夏日流行音樂，BPM 120，有鋼琴和吉他",
  "duration": 30,
  "title": "夏日晴天"
}
```

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| prompt | string | ✅ | 音樂描述（風格、樂器、情緒等） |
| duration | number | ❌ | 時長（秒，預設 30，最大 300） |
| title | string | ❌ | 音樂標題 |

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

### 3.5 影片生成

#### `POST /api/video`

文字或圖片生成影片（支援 MiniMax Hailuo-2.3）。

**Request（文字）：**
```json
{
  "prompt": "一隻可愛的貓在沙發上打哈欠",
  "duration": 5,
  "resolution": "720p"
}
```

**Request（圖片）：**
```json
{
  "image_url": "https://example.com/cat.png",
  "prompt": "貓緩慢地眨眼睛",
  "duration": 5
}
```

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| prompt | string | ✅（文字模式） | 影片描述 |
| image_url | string | ✅（圖片模式） | 參考圖片 URL |
| duration | number | ❌ | 秒數（預設 5，最大 30） |
| resolution | string | ❌ | 解析度 `720p` / `1080p`（預設 `720p`） |

**Response `200`（已同步完成）：**
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
  "message": "影片生成中，請使用 /api/video/{task_id} 查詢進度"
}
```

---

#### `GET /api/video/:task_id`

查詢影片生成進度。

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

### 3.6 歷史與工具

#### `GET /api/history`

取得當前 Session 的生成歷史（記憶體儲存）。

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

#### `GET /`

回傳嵌入式 HTML UI（單頁應用）。

#### `GET /health`

健康檢查端點。

**Response `200`：**
```json
{
  "status": "ok",
  "version": "1.1",
  "uptime_seconds": 3600
}
```

---

## 4. 前端 UI 佈局與元件

### 4.1 頁面結構

```
┌──────────────────────────────────────────────────┐
│  🔥 MiniMax Multi-Media Server                    │  ← 頁首（Logo + 名稱）
├──────────────────────────────────────────────────┤
│ [圖片生成] [YT封面] [圖片編輯] [語音] [音樂] [影片] │  ← Tab 按鈕列（含 YT 封面）
├──────────────────────────────────────────────────┤
│                                                  │
│  < 各 Tab 內容區 >                               │  ← Tab 內容（切換可見性）
│                                                  │
└──────────────────────────────────────────────────┘
```

### 4.2 Tab 元件說明

#### Tab 1：圖片生成（`#tab-generate`）
- Prompt 輸入框（textarea，max 2000 字）
- 寬高比下拉選單（1:1 / 16:9 / 9:16 / 4:3）
- 解析度下拉選單（1024x1024 / 512x512 / 768x768）
- **「生成圖片」按鈕** → POST `/api/generate`
- Loading 指示器（生成中顯示 spinner）
- 結果區：顯示圖片預覽 + 下載連結

#### Tab 2：YT 封面（`#tab-yt-thumbnail`）⭐ 可拖曳文字版
- Prompt 輸入框（描述縮圖主體背景，max 2000 字）
- 背景圖選擇器（橫向 thumbnail 列表，點擊切換；或留空以 AI 生成背景）
- **主標題輸入框**（max 80 字）+ 字體大小滑桿（24–120）+ 顏色選擇器
- **副標題輸入框**（max 120 字）+ 字體大小 + 顏色選擇器
- **文字陰影開關**（Toggle）
- **即時拖曳預覽區**（詳見 4.2.1）
- 風格預設按鈕群（🎬 Cinematic / 🌈 Vibrant / ⚪ Minimal / 🎭 Dramatic）
- 輸出格式切換（ JPG / PNG Radio）
- **「生成 YT 封面」按鈕** → POST `/api/yt-thumbnail`
- 結果區：預覽圖 + 下載連結
- 規格標籤：「1280×720px · 16:9 · YouTube 標準」

##### 4.2.1 即時拖曳預覽區（Canvas Preview）

```
+------------------------------------------+
|  [背景圖 full-bleed 顯示]                 |
|                                          |
|  ╔════════════════════════╗ ← 拖曳選中框   |
|  ║  主標題文字（可拖曳）    ║   8px dashed |
|  ╚════════════════════════╝   border      |
|                                          |
|  ┌────────────────────┐                   |
|  │ 副標題文字（可拖曳）  │                   |
|  └────────────────────┘                   |
+------------------------------------------+
```

**拖曳行為細節：**
- 點擊文字區塊 → 進入選中狀態（顯示 dashed border + 8 resize handles）
- 拖曳選中區塊 → 即时更新 DOM 位置，emit `onPositionChange`（debounced 300ms）
- 再次點擊其他位置 → 取消選中
- 位置以比例 `{ x: 0~1, y: 0~1 }` 儲存，與實際像素解耦
- Boundary clamp：文字區塊不可完全拖出可視區（留 5% padding）
- Touch 支援：`touchstart/touchmove/touchend` 對應 mouse 事件
- 最小觸控面積：44×44px（行動裝置友好）

**即時預覽流程：**
1. 使用者拖曳文字 → DOM 位置更新（無 API 呼叫）
2. 300ms debounce 後 → POST `/api/yt-thumbnail/preview`
3. 回傳 base64 data URI → 更新 `<img>` src
4. 若 API 逾時（5s），默默忽略，回退至 DOM-only 預覽

#### Tab 3：圖片編輯（`#tab-image2image`）
- 圖片上傳區（拖放或點擊上傳，支援 PNG/JPG/WebP）
- 參考圖預覽
- Prompt 輸入框
- 強度滑桿（0.0–1.0）
- **「開始編輯」按鈕** → POST `/api/image2image`
- 結果區：顯示原圖對比 + 結果圖預覽

#### Tab 4：語音（`#tab-tts`）
- 文字輸入框（textarea，max 1000 字）
- 聲音角色下拉選單
- 速度滑桿（0.5–2.0）
- **「生成語音」按鈕** → POST `/api/tts`
- 結果區：Audio Player 播放器 + 下載連結

#### Tab 5：音樂（`#tab-music`）
- Prompt 輸入框（描述音樂風格）
- 時長下拉選單（15s / 30s / 60s / 120s）
- 標題輸入框（選填）
- **「生成音樂」按鈕** → POST `/api/music`
- 結果區：Audio Player + 下載連結

#### Tab 6：影片（`#tab-video`）
- 模式切換（文字生成 / 圖片生成）
- Prompt 輸入框（或圖片 URL 輸入）
- 時長下拉（5s / 10s / 30s）
- **「生成影片」按鈕** → POST `/api/video`
- 進度輪詢區（每 3 秒輪詢 `/api/video/:task_id`）
- 結果區：Video Player + 下載連結

### 4.3 全域 UI 元件

| 元件 | 說明 |
|------|------|
| Header | 固定頂部，含伺服器名稱與版本 |
| Tab Bar | 水平按鈕列，作用中 Tab 有底線標示，YT 封面 Tab 領先指標（⭐ NEW 標籤） |
| Loading Spinner | 顯示在各操作按鈕下方，避免 UI 卡死 |
| Error Toast | 右下角彈出，3 秒後自動消失 |
| History Drawer | 右側滑出面板，顯示 `/api/history` 內容 |
| Download Button | 每個結果卡片下方有「下載」按鈕 |
| Responsive | 行動版 Tab 改為橫向滾動，結果卡片改單欄 |

---

## 5. 異常處理對應 HTTP 狀態碼

| HTTP 狀態碼 | 情境 |
|-------------|------|
| `200` | 成功讀取資料或任務建立（同步完成） |
| `201` | 非同步任務建立成功（需後續輪詢） |
| `400` | 請求參數錯誤（Prompt 為空、格式不符、長度超限） |
| `401` | 未設定 MiniMax API Key（`MINIMAX_API_KEY` 環境變數缺失） |
| `403` | API Key 無效或額度不足 |
| `404` | 資源不存在（影片任務 ID 找不到） |
| `409` | 資源衝突（通常不會在此系統發生） |
| `413` | 請求主體過大（圖片上傳超過 10MB） |
| `415` | 不支援的媒體格式（圖片上傳格式不符） |
| `422` | MiniMax API 回傳業務邏輯錯誤（如 Prompt 含敏感詞） |
| `429` | API 呼叫頻率超限（MiniMax 速率限制） |
| `500` | 伺服器內部錯誤（網路問題、MiniMax API 故障） |
| `502` | MiniMax API Gateway 錯誤 |
| `503` | MiniMax 服務暫時不可用 |

### 錯誤回應格式
```json
{
  "error": "錯誤描述訊息",
  "code": "ERROR_CODE",
  "details": {}
}
```

---

## 6. 實作約束

1. **API Key 注入**：`MINIMAX_API_KEY` 必須為環境變數，嚴禁寫入程式碼或設定檔。
2. **非同步任務儲存**：影片等非同步任務以 `Map<task_id, task_data>` 存在記憶體中，重啟後需重新查詢 MiniMax。
3. **圖片上傳大小限制**：前端與後端同步限制 10MB，防止攻擊。
4. **Prompt 長度限制**：各端點於 Express 層先做初步驗證（長度 + 非空），減輕 API 浪費。
5. **MiniMax API 封裝**：统一在 `src/server.ts` 或專用 module 封裝 axios 呼叫，隔離 HTTP 細節。
6. **Session-less**：伺服器不維護 Session，所有狀態來自請求本身或記憶體（history）。
7. **YT 封面文字疊加**：使用 sharp 的 `composite` 功能，標題文字先以 SVG 轉 PNG 圖層，再與主圖合成。

---

## 7. MiniMax API 型號對照

| 功能 | API 型號 | 備註 |
|------|----------|------|
| 圖片生成 | MiniMax image-01 | 高品質文字生成圖片 |
| **YT 封面生成** | **MiniMax image-01** | **固定 1280×720 + sharp 文字疊加** |
| 圖片編輯 | MiniMax image-01 (i2i) | 以圖片為參考的編輯 |
| 文字轉語音 | MiniMax speech-2.8-hd | 高清晰度語音合成 |
| 音樂生成 | MiniMax music-2.5 | 文字描述生成音樂 |
| 影片生成 | MiniMax Hailuo-2.3 | 文字/圖片生成影片（支援輪詢） |

---

## 8. Style 預設對照（YT 封面）

| Style | Prompt 前綴 | 視覺效果 |
|-------|-------------|---------|
| `cinematic` | `Cinematic lighting, film grain, dramatic shadows,` | 電影感，暗部細節豐富 |
| `vibrant` | `Vibrant colors, high contrast, sharp details,` | 高飽和，視覺衝擊強 |
| `minimal` | `Clean background, minimalist composition, soft lighting,` | 極簡，留白多 |
| `dramatic` | `Dramatic lighting, dark moody atmosphere, volumetric light,` | 戲劇性光影，暗調 |

---

## 9. 下一步

本規格文件經使用者確認後，交由 `backend-dev` Agent：
1. 依據現有 `src/index.ts` 結構實作 `/api/yt-thumbnail` 端點（含比例 position 解析）
2. 實作 `/api/yt-thumbnail/preview` 即時預覽端點（base64 回傳）
3. 在 `src/server.ts` 封裝 MiniMax image-01 呼叫
4. 使用 sharp 實作文字疊加圖層合成邏輯（SVG → PNG → composite，含 shadow）
5. 產出 `api-contract.md`

再交由 `frontend-dev` Agent：
6. 在 `const UI` 中新增 `#tab-yt-thumbnail` Tab 頁面
7. 實作 Canvas 拖曳預覽區（mousedown/mousemove/mouseup + touch 事件）
8. 實作 DraggableBox 元件，含 boundary clamp 與比例位置計算
9. 串接 `/api/yt-thumbnail/preview`（debounced 300ms）
10. 實作 YT 封面 Tab 的完整表單、背景選擇器、style 預設按鈕、結果預覽

---

Developed with 🐯 by 標虎團隊 | 技術總監: 匠 (Coder Agent)
