# 前端實作文件 — YT 封面生成 Tab

> **版本：** 1.0
> **建立日期：** 2026-04-17
> **負責 Agent：** frontend-dev
> **專案：** minimax-image-server
> **目標檔案：** `{project_root}/src/index.ts`（`const UI` 變數）
> **實作狀態：** ⚠️ 待實作（本 Agent 無法直接存取 project_root，須人工介入）

---

## 1. 實作限制說明

**⚠️ 重要：** 本 Agent 工作區受限於 `/Users/tigerclaw/claude/skills/agent-workflow`，無法直接修改 `/Users/tigerclaw/code/minimax-image-server/src/index.ts`。

**建議解決方案：**
1. 手動複製下方實作代碼至 `src/index.ts` 的 `const UI` 變數中
2. 或賦予本工作區存取 `minimax-image-server` 的權限

---

## 2. 需要修改的位置

### 2.1 Tab 按鈕列（需新增一項）

在 Tab 按鈕列中新增「YT 封面」按鈕：

```html
<button class="tab-btn" data-tab="generate">圖片生成</button>
<button class="tab-btn" data-tab="yt-thumbnail">YT 封面 ⭐</button>  <!-- 新增 -->
<button class="tab-btn" data-tab="image2image">圖片編輯</button>
<button class="tab-btn" data-tab="tts">語音</button>
<button class="tab-btn" data-tab="music">音樂</button>
<button class="tab-btn" data-tab="video">影片</button>
```

### 2.2 Tab 內容區（需新增一區）

在 `</div>` 關閉前新增 YT 封面 Tab 內容：

```html
<!-- Tab 內容 -->
<div id="generate" class="tab-content">...</div>
<div id="yt-thumbnail" class="tab-content">  <!-- 新增區塊 -->
  <div class="tab-inner">
    <h2>YT 封面生成</h2>
    <p class="spec-tag">1280×720px · 16:9 · YouTube 標準</p>

    <form id="yt-form" class="gen-form">
      <!-- Prompt 輸入 -->
      <div class="form-group">
        <label for="yt-prompt">縮圖主體描述</label>
        <textarea id="yt-prompt" name="prompt" rows="4"
          placeholder="例如：科技產品評測影片封面，暗色背景，左上角標題文字"
          maxlength="2000" required></textarea>
        <span class="char-count"><span id="yt-prompt-len">0</span>/2000</span>
      </div>

      <!-- 標題文字 -->
      <div class="form-group">
        <label for="yt-title">標題文字（選填）</label>
        <input type="text" id="yt-title" name="title_text"
          placeholder="例如：iPhone 16 評測" maxlength="100">
        <span class="form-hint">最多 100 字</span>
      </div>

      <!-- 字體大小 + 顏色 + 位置（橫排） -->
      <div class="form-row">
        <div class="form-group">
          <label for="yt-font-size">字體大小</label>
          <div class="range-wrapper">
            <input type="range" id="yt-font-size" name="title_font_size"
              min="24" max="120" value="72" step="4">
            <span id="yt-font-size-val">72px</span>
          </div>
        </div>

        <div class="form-group">
          <label>標題顏色</label>
          <div class="color-swatches">
            <input type="radio" name="yt-color" id="yt-color-white" value="#FFFFFF" checked>
            <label for="yt-color-white" class="swatch" style="background:#fff;border:1px solid #ccc" title="白色"></label>

            <input type="radio" name="yt-color" id="yt-color-black" value="#000000">
            <label for="yt-color-black" class="swatch" style="background:#000" title="黑色"></label>

            <input type="radio" name="yt-color" id="yt-color-yellow" value="#FFD700">
            <label for="yt-color-yellow" class="swatch" style="background:#FFD700" title="黃色"></label>

            <input type="radio" name="yt-color" id="yt-color-red" value="#FF3333">
            <label for="yt-color-red" class="swatch" style="background:#FF3333" title="紅色"></label>
          </div>
        </div>

        <div class="form-group">
          <label for="yt-position">標題位置</label>
          <select id="yt-position" name="title_position">
            <option value="top_left">左上</option>
            <option value="top_center">上中</option>
            <option value="bottom_left">左下</option>
            <option value="bottom_center" selected>下中</option>
          </select>
        </div>
      </div>

      <!-- 風格預設 -->
      <div class="form-group">
        <label>風格預設</label>
        <div class="style-buttons">
          <button type="button" class="style-btn active"
            data-style="cinematic" data-prefix="Cinematic lighting, film grain, dramatic shadows,">
            🎬 Cinematic
          </button>
          <button type="button" class="style-btn"
            data-style="vibrant" data-prefix="Vibrant colors, high contrast, sharp details,">
            🌈 Vibrant
          </button>
          <button type="button" class="style-btn"
            data-style="minimal" data-prefix="Clean background, minimalist composition, soft lighting,">
            ⚪ Minimal
          </button>
          <button type="button" class="style-btn"
            data-style="dramatic" data-prefix="Dramatic lighting, dark moody atmosphere, volumetric light,">
            🎭 Dramatic
          </button>
        </div>
        <input type="hidden" id="yt-style" name="style" value="cinematic">
      </div>

      <!-- 提交 -->
      <button type="submit" class="gen-btn" id="yt-submit">
        <span class="btn-text">生成 YT 封面</span>
        <span class="btn-loading" style="display:none">生成中...</span>
      </button>
    </form>

    <!-- 結果區 -->
    <div id="yt-result" class="result-box" style="display:none">
      <h3>生成完成</h3>
      <div class="preview-container">
        <img id="yt-preview" src="" alt="YT 封面預覽">
      </div>
      <p class="result-meta">
        <span id="yt-meta-resolution">1280×720px</span> ·
        <span id="yt-meta-style">cinematic</span>
      </p>
      <a id="yt-download" href="" download="yt-thumbnail.png" class="download-btn">
        下載原始圖片（1280×720）
      </a>
    </div>

    <!-- 錯誤區 -->
    <div id="yt-error" class="error-box" style="display:none"></div>
  </div>
</div>
<div id="image2image" class="tab-content">...</div>
```

### 2.3 JavaScript 邏輯（需新增至 `<script>` 區塊）

```javascript
// ========================================
// YT 封面 Tab JS
// ========================================

// 字數計數
const ytPrompt = document.getElementById('yt-prompt');
const ytPromptLen = document.getElementById('yt-prompt-len');
if (ytPrompt && ytPromptLen) {
  ytPrompt.addEventListener('input', () => {
    ytPromptLen.textContent = ytPrompt.value.length;
  });
}

// 字體大小滑桿即時顯示
const ytFontSize = document.getElementById('yt-font-size');
const ytFontSizeVal = document.getElementById('yt-font-size-val');
if (ytFontSize && ytFontSizeVal) {
  ytFontSize.addEventListener('input', () => {
    ytFontSizeVal.textContent = ytFontSize.value + 'px';
  });
}

// 風格預設按鈕切換
document.querySelectorAll('.style-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.style-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const styleInput = document.getElementById('yt-style');
    if (styleInput) styleInput.value = btn.dataset.style;
  });
});

// YT 封面表單提交
const ytForm = document.getElementById('yt-form');
if (ytForm) {
  ytForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const submitBtn = document.getElementById('yt-submit');
    const btnText = submitBtn?.querySelector('.btn-text');
    const btnLoading = submitBtn?.querySelector('.btn-loading');
    const resultBox = document.getElementById('yt-result');
    const errorBox = document.getElementById('yt-error');

    // UI 狀態：開始
    if (submitBtn) submitBtn.disabled = true;
    if (btnText) btnText.style.display = 'none';
    if (btnLoading) btnLoading.style.display = 'inline';
    if (resultBox) resultBox.style.display = 'none';
    if (errorBox) errorBox.style.display = 'none';

    try {
      const prompt = document.getElementById('yt-prompt')?.value?.trim();
      if (!prompt) throw new Error('Prompt 不能為空');

      const payload = {
        prompt,
        title_text: document.getElementById('yt-title')?.value?.trim() || undefined,
        title_font_size: parseInt(document.getElementById('yt-font-size')?.value || '72'),
        title_color: document.querySelector('input[name="yt-color"]:checked')?.value || '#FFFFFF',
        title_position: document.getElementById('yt-position')?.value || 'bottom_center',
        style: document.getElementById('yt-style')?.value || 'cinematic',
      };

      const res = await fetch('/api/yt-thumbnail', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const json = await res.json();
      if (!res.ok) throw new Error(json.error || 'YT 封面生成失敗');

      // 顯示結果
      const preview = document.getElementById('yt-preview');
      const download = document.getElementById('yt-download');
      const metaStyle = document.getElementById('yt-meta-style');
      if (preview) preview.src = json.image_url;
      if (download) {
        download.href = json.image_url;
        download.download = `yt-thumbnail-${json.task_id}.png`;
      }
      if (metaStyle) metaStyle.textContent = json.style || payload.style;
      if (resultBox) resultBox.style.display = 'block';

      // 加入歷史
      addToHistory({ task_id: json.task_id, type: 'yt_thumbnail', prompt, result_url: json.image_url });

    } catch (err) {
      if (errorBox) {
        errorBox.textContent = err.message;
        errorBox.style.display = 'block';
      }
    } finally {
      if (submitBtn) submitBtn.disabled = false;
      if (btnText) btnText.style.display = 'inline';
      if (btnLoading) btnLoading.style.display = 'none';
    }
  });
}
```

### 2.4 CSS 樣式（需新增）

```css
/* YT 封面 Tab */
.spec-tag {
  display: inline-block;
  background: #e8f4fd;
  color: #1976d2;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  margin-bottom: 16px;
}

.range-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
}

.range-wrapper input[type="range"] {
  flex: 1;
}

.range-wrapper span {
  min-width: 40px;
  text-align: right;
  font-size: 13px;
  color: #555;
}

.color-swatches {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 4px;
}

.color-swatches input[type="radio"] {
  display: none;
}

.color-swatches .swatch {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  cursor: pointer;
  display: inline-block;
  transition: transform 0.15s, box-shadow 0.15s;
}

.color-swatches input[type="radio"]:checked + .swatch {
  box-shadow: 0 0 0 3px #fff, 0 0 0 5px #1976d2;
  transform: scale(1.1);
}

.style-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 6px;
}

.style-btn {
  padding: 8px 16px;
  border: 2px solid #ddd;
  border-radius: 20px;
  background: #fff;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.style-btn:hover {
  border-color: #1976d2;
  background: #f0f7ff;
}

.style-btn.active {
  border-color: #1976d2;
  background: #e3f2fd;
  color: #1565c0;
  font-weight: 600;
}

.preview-container {
  background: #1a1a2e;
  border-radius: 8px;
  padding: 12px;
  margin: 12px 0;
  text-align: center;
}

.preview-container img {
  max-width: 100%;
  max-height: 400px;
  border-radius: 4px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.3);
}

.result-meta {
  color: #666;
  font-size: 13px;
  margin: 8px 0;
}
```

---

## 3. API 對應

| 前端元件 | API 端點 | Method |
|----------|----------|--------|
| YT 封面表單 | `/api/yt-thumbnail` | POST |

**請求格式：**
```json
{
  "prompt": "科技產品評測影片封面，暗色背景",
  "title_text": "iPhone 16 評測",
  "title_font_size": 72,
  "title_color": "#FFFFFF",
  "title_position": "bottom_center",
  "style": "cinematic"
}
```

**成功回應：**
```json
{
  "success": true,
  "task_id": "yt_abc123",
  "image_url": "https://cdn.minimax.io/...",
  "resolution": "1280x720"
}
```

---

## 4. Style 前綴對照（後端參考）

| Style | Prompt 前綴 |
|-------|-------------|
| `cinematic` | `Cinematic lighting, film grain, dramatic shadows,` |
| `vibrant` | `Vibrant colors, high contrast, sharp details,` |
| `minimal` | `Clean background, minimalist composition, soft lighting,` |
| `dramatic` | `Dramatic lighting, dark moody atmosphere, volumetric light,` |

---

## 5. 實作檢查清單

- [ ] Tab 按鈕列新增「YT 封面」按鈕（含 ⭐ 標示）
- [ ] Tab 內容區新增 `#yt-thumbnail` 區塊
- [ ] Prompt textarea 含字數計數（即時更新）
- [ ] 標題文字輸入框（max 100）
- [ ] 字體大小滑桿（24–120px，即時顯示數值）
- [ ] 標題顏色選擇器（白/黑/黃/紅，radio button + swatch）
- [ ] 標題位置下拉（top_left/top_center/bottom_left/bottom_center）
- [ ] 風格預設按鈕群（4 種，點擊切換 active 狀態）
- [ ] 規格標籤顯示「1280×720px · 16:9 · YouTube 標準」
- [ ] 表單提交 POST `/api/yt-thumbnail`
- [ ] Loading 狀態（按鈕禁用 + 文字切換）
- [ ] 結果區：預覽圖 + 下載連結 + 規格 meta
- [ ] 錯誤區：紅色提示框
- [ ] 全域 Tab 切換邏輯已支援新 Tab

---

Developed with 🐯 by 標虎團隊 | 技術總監: 匠 (Coder Agent)
