# 前端元件規格文件

> **版本：** 1.0
> **建立日期：** 2026-04-17
> **負責 Agent：** frontend-dev
> **實作狀態：** ✅ 已完成（2026-04-17）

---

## 1. 技術架構

| 項目 | 說明 |
|------|------|
| 框架 | Flask（Jinja2 模板引擎） |
| 前端 | HTML5 / CSS3 / Vanilla JS（無框架依賴） |
| 圖示 | Emoji 文字（無外部圖示庫） |
| 字體 | `'Helvetica Neue', Helvetica, Arial, 'PingFang TC', 'Microsoft JhengHei'` |
| 響應式斷點 | 桌面 >768px / 手機 ≤768px |
| Session 管理 | sessionStorage（會員 client-side） |

---

## 2. 模板檔案結構

```
{project_root}/
├── app.py                      # Flask 應用程式（含所有路由）
├── config.py                   # 資料庫與 Session 設定
├── database.py                 # SQLite 工具與 Schema
└── templates/                  # Jinja2 範本
    ├── index.html              # 顧客首頁（著陸頁）
    ├── order.html              # 顧客點餐頁（主要 UI）
    ├── admin.html              # 管理後台儀表板
    └── admin_login.html        # 管理者登入頁
    └── customer/
        └── index.html          # 備援單頁 UI（含所有 tab）
```

---

## 3. 顧客端頁面

### 3.1 `index.html` — 著陸首頁

**用途：** 品牌展示、吸引顧客開始點餐。

**路由：** `GET /`（`app.py` 的 `index()`）

**主要內容區塊：**
- **Hero 橫幅**：標語、按鈕「開始點餐」→ `/order`
- **特色亮點**：3 個卡片（現點現做、會員積點、線上點餐）
- **精選菜單預覽**：取前 4 項，`GET /api/menu`
- **會員 CTA 區**：登入/註冊呼籲（已登入隱藏）
- **頁尾**：品牌名、連結

**Modals：**
| Modal ID | 用途 | 觸發 |
|----------|------|------|
| `#loginModal` | 會員登入表單 | 導覽列「會員登入」、CTA |
| `#registerModal` | 會員註冊表單 | 導覽列「加入會員」、CTA |
| `#pointsModal` | 點數查詢（含歷史） | 導覽列「我的點數」 |

**Session 儲存：** `sessionStorage.member`（含 `member_id`, `name`, `phone`, `points`）

---

### 3.2 `order.html` — 點餐頁（主要 UI）

**用途：** 完整點餐流程（瀏覽→加入購物車→結帳→查詢）。

**路由：** `GET /order`（已於 `app.py` 補充）

**左右雙欄佈局（桌面 ≥769px）：**
```
┌──────────────────────────┬──────────────────┐
│  左側：菜單區            │  右側：購物車     │
│  ├─ 分類篩選 tab         │  ├─ 品項列表      │
│  └─ 品項卡片網格         │  ├─ 點數折抵輸入  │
│                          │  └─ 價格摘要      │
└──────────────────────────┴──────────────────┘
```

**功能邏輯：**
- `GET /api/menu` → 動態渲染分類 + 品項
- 分類切換即時過濾（client-side）
- 加入購物車：一次加 1 筆（+按鈕或「+ 加入」按鈕）
- 購物車支援：增、減、刪品項
- 會員折抵：`getRedeemAmount()` 取 min(輸入值, 可用點數, 小計)
- 結帳 Modal：顧客資料 + 即時摘要更新
- `POST /api/checkout` → 成功後顯示成功 Modal、清除購物車

**查詢訂單區（`#lookup` anchor）：**
- `GET /api/orders?phone=xxx` → 渲染訂單列表
- 狀態 badge：pending（等待中）、preparing（製作中）、completed（已完成）、cancelled（已取消）

---

### 3.3 `customer/index.html` — 單頁全功能 UI（備援）

**用途：** 單一 HTML 檔包含所有前台功能（Tab 切換式）。

**Tab 結構：**
| Tab | 內容 |
|-----|------|
| `#menu` | 菜單瀏覽 + 分類篩選 |
| `#cart` | 購物車 + 結帳表單 |
| `#orders` | 我的訂單列表 + 詳情 Modal |
| `#member` | 登入/註冊 表單切換、會員資訊、點數歷史 |

> 此檔案為完整自包含 HTML，獨立運作不需要 Flask 路由（可作為 PWA 或純靜態替代方案）。

---

## 4. 管理後台頁面

### 4.1 `admin_login.html` — 管理者登入

**路由：** `GET /admin/login`

**表單欄位：**
| 欄位 | 型別 | 驗證 |
|------|------|------|
| 帳號 | text | required |
| 密碼 | password | required |

**行為：**
- `POST /admin/login` → Flask session 管理 → 成功 302 到 `/admin/orders`
- 登入失敗：Flash message 顯示錯誤訊息

**樣式：** 單卡式登入（置中卡片，暗色主題，紅色品牌強調）

---

### 4.2 `admin.html` — 管理儀表板

**路由：** `GET /admin/orders`（需管理者 session）

**Sidebar 導覽（3 個 Tab）：**

| Sidebar Tab | 對應 section | 功能 |
|-------------|--------------|------|
| 📋 訂單管理 | `#tabOrders` | 狀態篩選、訂單列表、接單/完成/取消 |
| 📊 日報表 | `#tabReport` | 日期選擇、統計卡片、品項排行 |
| 👥 會員管理 | `#tabMembers` | 電話搜尋、會員卡片列表、詳情 Modal |

**訂單管理 Tab：**
- 狀態篩選：全部 / 等待中 / 製作中 / 已完成 / 已取消（即時篩選 + 重新整理按鈕）
- 統計列：總訂單、等待中、製作中、已完成（即時更新）
- 表格：`GET /api/admin/orders` → 狀態即時更新按鈕
- 詳情 Modal：`GET /api/orders/<id>` + `PUT /api/admin/orders/<id>/status`

**會員管理 Tab：**
- 電話模糊搜尋：`GET /api/admin/members?phone=xxx`
- 會員卡片：名稱、電話、可用點數、加入時間
- 詳情 Modal（含點數調整）：
  - 消費紀錄列表
  - 點數歷史（累積 / 折抵 / 調整）
  - 手動調整表單：`PUT /api/admin/members/<id>/points`

**日報表 Tab：**
- 日期選擇器（預設今天）
- 6 格統計卡：總訂單、總營收、已完成、等待中、製作中、已取消
- 熱銷品項排行（`GET /api/reports/daily?date=xxx`）

**管理者登出：** `POST /admin/logout` → 清除 session → 302 回 `/admin/login`

---

## 5. 全域 UI 組件

### 5.1 頂部導覽列（`site-header`）

出現在所有頁面（sticky）：
- 左：品牌名（連結至首頁）
- 右：功能連結 + 會員狀態（已登入：姓名 + 點數 + 登出按鈕；未登入：登入/註冊按鈕）
- 手機：漢堡選單（`.hamburger`）

### 5.2 Toast 通知

樣式：圓角深色橢圓，底部居中，2.5 秒後淡出。
JS 函式：`showToast(msg)` / `toast(msg)`

### 5.3 Modal 系統

- 點擊遮罩（`.modal-overlay`）自動關閉
- 所有 Modal 有 `role="dialog"`, `aria-modal="true"`
- 表單提交前 `e.preventDefault()` 避免頁面跳轉

### 5.4 狀態 Badge

| 狀態 | CSS Class | 背景色 |
|------|-----------|--------|
| pending（等待中） | `.status-pending` | `#fef3c7` 琥珀 |
| preparing（製作中） | `.status-preparing` | `#dbeafe` 藍 |
| completed（已完成） | `.status-completed` | `#d1fae5` 綠 |
| cancelled（已取消） | `.status-cancelled` | `#fee2e2` 灰紅 |

---

## 6. API 呼叫模式

**工具函式：**
```javascript
async function apiFetch(url, opts = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(json.error || '請求失敗'), { status: res.status });
  return json;
}
```

**錯誤處理：** 所有 API 錯誤轉為 `Error` 擲出，由各頁面 `try/catch` 捕捉並顯示 Toast 或 `form-error` 區塊。

---

## 7. 設計語言

| 屬性 | 值 |
|------|----|
| 主色 | `#c0392b`（深紅） |
| 主色 dark | `#a93226` |
| 強調色 | `#e67e22`（橙） |
| 深色/頁尾 | `#2c2c2c` |
| 背景 | `#faf7f2`（米白） |
| 背景-alt | `#f0ebe3` |
| 成功色 | `#27ae60` |
| 危險色 | `#e74c3c` |
| 圓角（預設） | `8px` |
| 圓角（大） | `12px` |
| 陰影 | `0 2px 8px rgba(0,0,0,0.08)` |

---

## 8. 無障礙（a11y）

- 所有按鈕有明確文字內容（不以 icon 替代）
- Modal 設 `role="dialog"`, `aria-modal="true"`
- 表單 `<label>` 明確關聯 `for/id`
- `focus` 狀態可見（`outline` 或 `box-shadow`）
- 色彩對比符合 WCAG AA（主色 `#c0392b` 在白底 `faf7f2` 的對比度 > 4.5:1）
