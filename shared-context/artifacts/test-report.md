# 測試報告（test-report.md）

> **版本：** 1.1
> **建立日期：** 2026-04-17
> **更新日期：** 2026-04-18
> **負責 Agent：** tester
> **專案：** minimax-image-server
> **測試框架：** Jest + ts-jest + Supertest + nock
> **覆蓋範圍：** 圖片生成、圖片編輯、**YT 封面生成**、TTS、音樂、影片、健康檢查
> **本輪重點：** SPEC.md 格式驗收 ✅ 已通過

---

## 0. SPEC.md 格式驗收（Round 1 本輪）

> **執行時間：** 2026-04-18
> **檢查目標：** `{artifacts_dir}/SPEC.md`
> **結果：** ✅ **通過**

### 必要區段對照

| config.yaml 要求 | SPEC.md 對應位置 | 結果 |
|-----------------|-----------------|------|
| 功能範圍與 YAGNI 邊界 | Section 2（2.1 In Scope / 2.2 Out of Scope） | ✅ |
| API 端點（request/response 格式） | Section 3（3.1–3.6，含所有 9 個端點） | ✅ |
| 前端 UI 佈局與元件 | Section 4（4.1–4.3，含 Tab 結構、規格標籤） | ✅ |
| 異常處理對應 HTTP 狀態碼 | Section 5（含狀態碼對照表 + 錯誤 JSON 格式） | ✅ |

### API 端點覆蓋（Section 3）

| 端點 | Request 格式 | Response 格式 | 異常處理 | 結果 |
|------|-------------|--------------|---------|------|
| `POST /api/generate` | ✅ JSON | ✅ JSON | ✅ 400/500 | ✅ |
| `POST /api/image2image` | ✅ multipart/form-data | ✅ JSON | ✅ 400/413/415 | ✅ |
| `POST /api/yt-thumbnail` | ✅ JSON | ✅ JSON | ✅ 400/500 | ✅ |
| `POST /api/tts` | ✅ JSON | ✅ JSON | ✅ 400 | ✅ |
| `POST /api/music` | ✅ JSON | ✅ JSON | ✅ 400 | ✅ |
| `POST /api/video` | ✅ JSON | ✅ 同步/非同步 | ✅ | ✅ |
| `GET /api/video/:task_id` | ✅ Path param | ✅ JSON | ✅ 404 | ✅ |
| `GET /api/history` | — | ✅ JSON | — | ✅ |
| `GET /health` | — | ✅ JSON | — | ✅ |

**全部 9 個端點已完整記錄，含 request example、response example、錯誤格式。**

### ⚠️ 待確認事項（低優先級）

| 項目 | 說明 |
|------|------|
| `src/server.ts` 提及 | Section 6 提及此檔案，但 config.yaml 僅說明 `src/index.ts` 為主入口；確認是否需建立 `server.ts` 或以此為參照模組 |
| 拖曳調整功能 | Section 4 的 YT 封面 Tab 未提及拖曳互動；`title_position` 欄位已定義，拖曳屬前端實作細節，不影響 API 合約 |

**結論：** SPEC.md 格式符合 `analyzer` Agent 產出要求，可進入 `backend-dev` 實作階段。

---

## 1. 測試檔案架構

```
tests/
├── setup.ts                   # Jest 全域設定（dotenv + timeout + API Key mock）
├── conftest.ts                # Jest 全域 helper（Supertest agent、nock、assertion utils）
├── test_generate.test.ts       # POST /api/generate
├── test_image2image.test.ts    # POST /api/image2image
├── test_yt_thumbnail.test.ts   # POST /api/yt-thumbnail  ⭐ 新增
├── test_tts.test.ts           # POST /api/tts
├── test_music.test.ts         # POST /api/music
├── test_video.test.ts         # POST /api/video + GET /api/video/:task_id
└── test_health.test.ts       # GET /health + GET /api/history + GET /
```

**⚠️ 注意：** 由於路徑許可限制，測試程式碼寫入 `{artifacts_dir}/tests/`。正式使用時需複製至 `{project_root}/tests/`：

```bash
cp -r {artifacts_dir}/tests/ {project_root}/tests/
cp {artifacts_dir}/jest.config.js {project_root}/jest.config.js
```

並確認以下依賴已安裝：

```bash
npm install --save-dev jest ts-jest @types/jest supertest nock
```

---

## 2. 測試隔離策略

| 策略 | 說明 |
|------|------|
| 獨立 app instance | 每個 `beforeAll` 重新 `createApp()`，避免測試間共享狀態 |
| nock HTTP mock | 所有 MiniMax API 呼叫被 nock 攔截，回傳假 CDN URL |
| Session 記憶體隔離 | 每個 Supertest agent 維護獨立 session（`GET /api/history` 測試） |
| `afterEach` 清場 | 每個測試後呼叫 `nock.cleanAll()`，防止 mock 殘留 |
| `process.env` 恢復 | API Key 測試後還原環境變數（不做 `delete`，用 `originalKey` 暫存） |

---

## 3. 測試覆蓋矩陣

### 3.1 圖片生成（`test_generate.test.ts`）

| 測試 | 情境 | 預期 HTTP |
|------|------|-----------|
| `回應 200 且包含 success、task_id、image_url` | 正常 Prompt | 200 |
| `回應包含 prompt 與 created_at` | 驗證 response 欄位 | 200 |
| `支援自訂 aspect_ratio 與 resolution` | 驗證參數傳遞 | 200 |
| `prompt 為空 → 400` | 未填 Prompt | 400 |
| `prompt 未攜帶 → 400` | 完全無 prompt 欄位 | 400 |
| `prompt 長度超限（> 2000 字）→ 400` | 2001 字測試 | 400 |
| `未設定 API Key → 401` | 刪除 MINIMAX_API_KEY | 401 |
| `MiniMax API 失敗 → 500` | HTTP 500 mock | 500 |
| `MiniMax 業務錯誤 422 → 422` | 回傳 422 | 422 |
| `API 頻率限制 429 → 429` | 回傳 429 | 429 |

**小計：10 測試**

### 3.2 圖片編輯（`test_image2image.test.ts`）

| 測試 | 情境 | 預期 HTTP |
|------|------|-----------|
| `回應 200，含 task_id、image_url、original_filename` | 正常上傳 + Prompt | 200 |
| `支援 strength 參數（0.0–1.0）` | 驗證 strength 傳遞 | 200 |
| `未上傳圖片 → 400` | 只有 Prompt，無 image 欄位 | 400 |
| `Prompt 為空 → 400` | 空字串 Prompt | 400 |
| `不支援的檔案格式（.gif）→ 415` | Content-Type 非 PNG/JPG/WebP | 415 |
| `MiniMax API 失敗 → 500` | HTTP 500 mock | 500 |

**小計：6 測試**

### 3.3 文字轉語音（`test_tts.test.ts`）

| 測試 | 情境 | 預期 HTTP |
|------|------|-----------|
| `回應 200，含 audio_url、duration_seconds` | 正常 TTS | 200 |
| `支援自訂 voice、speed、pitch` | 驗證參數傳遞 | 200 |
| `text 為空 → 400` | 空字串 | 400 |
| `text 未攜帶 → 400` | 完全無 text | 400 |
| `text 長度超限（> 1000 字）→ 400` | 1001 字測試 | 400 |
| `MiniMax API 失敗 → 500` | HTTP 500 mock | 500 |

**小計：6 測試**

### 3.4 音樂生成（`test_music.test.ts`）

| 測試 | 情境 | 預期 HTTP |
|------|------|-----------|
| `回應 200，含 audio_url、duration_seconds、title` | 正常音樂生成 | 200 |
| `支援自訂 duration` | 60 秒測試 | 200 |
| `prompt 為空 → 400` | 空字串 | 400 |
| `prompt 未攜帶 → 400` | 完全無 prompt | 400 |
| `duration 超過上限（> 300s）→ 400` | 400 秒測試 | 400 |
| `MiniMax API 失敗 → 500` | HTTP 500 mock | 500 |

**小計：6 測試**

### 3.5 影片生成（`test_video.test.ts`）

| 測試 | 情境 | 預期 HTTP |
|------|------|-----------|
| `文字模式：回應 200，含 video_url` | 純文字 Prompt | 200 |
| `圖片模式：回應 200，含 video_url` | 攜帶 image_url | 200 |
| `支援自訂 duration 與 resolution` | 驗證參數傳遞 | 200 |
| `prompt 與 image_url 皆未攜帶 → 400` | 完全無內容 | 400 |
| `duration 超過上限（> 30s）→ 400` | 60 秒測試 | 400 |
| `任務已完成：含 status=completed、video_url` | GET 查詢已完成任務 | 200 |
| `任務不存在 → 404` | 不存在的 task_id | 404 |
| `MiniMax API 失敗 → 500` | HTTP 500 mock | 500 |

**小計：8 測試**

### 3.6 健康檢查（`test_health.test.ts`）

| 測試 | 情境 | 預期 HTTP |
|------|------|-----------|
| `GET /health → 200，含 status、version、uptime_seconds` | 健康檢查端點 | 200 |
| `GET /api/history → items=[]、total=0`（初始空） | 新 session | 200 |
| `generate 後 history 包含新項目` | 驗證歷史記錄寫入 | 200 |
| `GET / → Content-Type: text/html` | HTML UI | 200 |
| `HTML 包含 Tab 按鈕結構` | 驗證 UI 內容 | 200 |

**小計：5 測試**

### 3.7 YT 封面生成（`test_yt_thumbnail.test.ts`）

| 測試 | 情境 | 預期 HTTP |
|------|------|-----------|
| `回應 200，含 task_id、image_url、resolution=1280x720` | 正常生成 | 200 |
| `回應包含 prompt、title_text、created_at` | 驗證 response 欄位 | 200 |
| `支援自訂標題參數（font_size、color、position）` | 完整參數傳遞 | 200 |
| `無標題文字時也能正常生成（title_text 選填）` | title_text 選填 | 200 |
| `style="cinematic" → 回應 200` | Cinematic 風格 | 200 |
| `style="vibrant" → 回應 200` | Vibrant 風格 | 200 |
| `style="minimal" → 回應 200` | Minimal 風格 | 200 |
| `style="dramatic" → 回應 200` | Dramatic 風格 | 200 |
| `title_position="top_left" → 回應 200` | 左上位置 | 200 |
| `title_position="top_center" → 回應 200` | 上中位置 | 200 |
| `title_position="bottom_left" → 回應 200` | 左下位置 | 200 |
| `title_position="bottom_center" → 回應 200` | 下中位置 | 200 |
| `prompt 為空 → 400` | 未填 Prompt | 400 |
| `prompt 未攜帶 → 400` | 完全無 prompt 欄位 | 400 |
| `prompt 長度超限（> 2000 字）→ 400` | 2001 字測試 | 400 |
| `title_text 超過 100 字 → 400` | 101 字標題 | 400 |
| `style 為非有效值 → 400` | invalid_style 值 | 400 |
| `title_font_size < 24 → 400` | 字體過小 | 400 |
| `title_font_size > 120 → 400` | 字體過大 | 400 |
| `title_color 為非十六進位格式 → 400 或 200` | 顏色格式錯誤 | 400/200 |
| `MiniMax API 失敗 → 500` | HTTP 500 mock | 500 |
| `MiniMax API 回傳業務錯誤 422 → 422` | 敏感詞屏蔽 | 422 |
| `API 頻率限制 429 → 回傳 429` | 回傳 429 | 429 |
| `未設定 API Key → 401` | 刪除 MINIMAX_API_KEY | 401 |

**小計：23 測試**

---

**總計：64 測試案例**

---

## 4. Mock 工具鏈說明

### 4.1 nock

用於攔截 `https://api.minimax.io` 的 HTTP 請求，回傳可控的假回應：

```typescript
nock('https://api.minimax.io')
  .post('/v1/image_generation')
  .reply(200, {
    code: 0,
    msg: 'success',
    data: {
      task_id: 'img_test123',
      image_url: 'https://cdn.minimax.io/image/abc123.png',
    },
  });
```

### 4.2 假 CDN URL

`fakeMinimaxUrl()` helper 動態產生 `https://cdn.minimax.io/{type}/{random_id}.{ext}`，確保 response URL 格式正確且不重複。

### 4.3 MiniMax API 端點對照

| 功能 | Mock 端點 |
|------|-----------|
| 圖片生成 | `POST /v1/image_generation` |
| 圖片編輯 | `POST /v1/image_generation` |
| **YT 封面生成** | **`POST /v1/image_generation`**（固定 1280×720 + style 前綴） |
| TTS | `POST /v1/t2a_v2` |
| 音樂生成 | `POST /v1/music_generation` |
| 影片生成 | `POST /v1/video_generation` |

---

## 5. 執行方式

```bash
cd /Users/tigerclaw/code/minimax-image-server

# 安裝依賴（如尚未安裝）
npm install --save-dev jest ts-jest @types/jest supertest nock

# 執行所有測試
npm test

# 執行特定模組
npm test -- --testPathPattern=test_generate

# 含覆蓋率
npm test -- --coverage

# 單次執行（watch mode 關閉）
npm test -- --watchAll=false
```

**預期輸出（全部通過）：**
```
PASS  tests/test_generate.test.ts
PASS  tests/test_image2image.test.ts
PASS  tests/test_yt_thumbnail.test.ts  ⭐ 新增
PASS  tests/test_tts.test.ts
PASS  tests/test_music.test.ts
PASS  tests/test_video.test.ts
PASS  tests/test_health.test.ts
==================== 64 passed in 5.xx s ====================
```

---

## 6. 待後端實作確認的事項

以下為測試預期行為，需 `backend-dev` Agent 對應實作：

1. **電話格式驗證**：正則表達式 `^09\d{8}$`，需在 `/api/members/register` 實作（目前訂餐系統無此端點，本專案為多媒體伺服器，無會員系統）
2. **Session 管理**：`GET /api/history` 依賴記憶體 Map（已在 `backend-dev` 實作）
3. **圖片上傳處理**：需支援 `multipart/form-data`（multer），同時支援 PNG/JPG/WebP
4. **記憶體 DB**：Flask app `createApp()` 需支援 `DATABASE` config（不適用於本 Express 專案）
5. **`createApp()` 導出**：測試需要 `import { createApp } from '../src/index'`，確認 src/index.ts 有導出 `createApp`
6. **`POST /api/yt-thumbnail`**：`style` 預設前綴轉譯（cinematic/vibrant/minimal/dramatic → prompt 前綴）、sharp 文字疊加（SVG → PNG → composite）、固定解析度 1280×720、`title_text` 長度驗證（≤100 字）、`title_font_size` 範圍驗證（24–120）

---

## 7. 建議改進（YAGNI 範圍外）

| 項目 | 說明 |
|------|------|
| `msw`（Mock Service Worker） | 取代 nock，支援更完整的 REST mock 情境 |
| `pytest-randomly` 之於 Jest | `jest --randomize` 發現順序依賴 |
| 整合 GitHub Actions CI | `jest --coverage` 在每次 PR 自動執行 |
| API 快照測試 | 使用 `jest-fetch-mock` + `expectSnapshot()` |
| Error boundary 測試 | 模擬 MiniMax API 各種 5xx 錯誤 |
| 圖片上傳單元測試 | 使用 `form-data` 或直接構造 `FormData` 物件 |

---

Developed with 🐯 by 標虎團隊 | 技術總監: 匠 (Coder Agent)
