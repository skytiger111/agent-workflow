# Bug 4 修復：多專案 Artifacts 衝突 — 實作計劃

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `shared-context/artifacts/` 改為 `{WORKFLOW_DIR}/projects/{project_name}/artifacts/`，每個專案有獨立目錄，不再互相覆蓋。

**Architecture:** 從 `${WORKFLOW_DIR}/shared-context/artifacts/` 集中式，改為 `${WORKFLOW_DIR}/projects/{project_name}/artifacts/` 專案隔離式。`project_name` 從 config 的 `name` 或 `project_root` 目錄名推斷。

**Tech Stack:** Bash + Python (Flask)

---

## 受影響檔案

- Modify: `runner.sh` — `ARTIFACTS_DIR` 改動態路徑、`init_dirs()`、`load_config()`、`jq_get()`、`write_handoff()`
- Modify: `lib/handoff.py` — `ARTIFACTS` 路徑動態化
- Modify: `app.py` — `ARTIFACTS_DIR` + `list_artifacts()`
- Modify: `templates/workflow_ui.html` — 讀取動態 artifacts 路徑
- Modify: `tests/test_pipeline_api.py` — 新增 per-project artifacts 測試

---

## 檔案現況摘要

**runner.sh** 目前：
- `CONTEXT_DIR="${WORKFLOW_DIR}/shared-context"`（第14行，固定）
- `ARTIFACTS_DIR="${CONTEXT_DIR}/artifacts"`（第15行，固定）
- `load_config()` 只讀 `project_root`、`git_remote`、`git_branch`、`handoff_footer`，**未讀 `name`**
- `init_dirs()` 直接 `mkdir -p "$ARTIFACTS_DIR"`

**lib/handoff.py** 目前：
- `ARTIFACTS` 是模組層級常數（第13-19行），固定寫死 `shared-context/artifacts/`

**app.py** 目前：
- `SHARED = os.path.join(BASE_DIR, "shared-context")`（固定）
- `ARTIFACTS_DIR = os.path.join(SHARED, "artifacts")`（固定）

---

## Task 1：runner.sh — 動態 ARTIFACTS_DIR

### 修改：runner.sh

- [ ] **Step 1: 讀取 `name` 欄位（若無則從 `project_root` 目錄名推斷）**

在 `load_config()` 的 Python block 裡，加入讀取 `name` 的邏輯，並在函式結尾設定 `ARTIFACTS_DIR`。

```bash
# load_config() 中，在讀完 yaml 後新增：
PROJECT_NAME=$(python3 -c "
import yaml, sys, os
with open('$cfg') as f:
    cfg = yaml.safe_load(f)
name = cfg.get('name', '')
if not name:
    root = cfg.get('project_root', '')
    name = os.path.basename(os.path.abspath(root)) if root else 'default'
print(name)
" 2>/dev/null || echo "default")

ARTIFACTS_DIR="${WORKFLOW_DIR}/projects/${PROJECT_NAME}/artifacts"
```

- [ ] **Step 2: 更新 `init_dirs()` 使用正確路徑**

`init_dirs()` 保持不變（已用 `$ARTIFACTS_DIR`），但需確保 `mkdir -p` 會建立 `projects/{name}/artifacts` 的完整路徑。

- [ ] **Step 3: 驗證**

```bash
cd /Users/tigerclaw/claude/skills/agent-workflow
CONFIG_FILE="config.market-sentiment.yaml" source runner.sh 2>&1 | head -5
# 預期：ARTIFACTS_DIR 變成 .../projects/market-sentiment/artifacts
```

---

## Task 2：lib/handoff.py — 動態 ARTIFACTS 路徑

### 修改：lib/handoff.py

- [ ] **Step 1: 移除模組層級 `ARTIFACTS` 常數，改由 `cmd_init()` 動態產生**

```python
# 移除第13-19行的 ARTIFACTS 常數，改為函式內產生
def _make_artifacts(base):
    return {
        "spec": f"{base}/SPEC.md",
        "api_contract": f"{base}/api-contract.md",
        "frontend_spec": f"{base}/component-spec.md",
        "test_report": f"{base}/test-report.md",
        "deploy_status": f"{base}/deploy-status.md",
    }

def cmd_init():
    ...
    # 讀取 PROJECT_NAME（第4個額外參數）
    project_name = sys.argv[4] if len(sys.argv) > 4 else "default"
    artifacts_base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "projects", project_name, "artifacts")
    art_paths = _make_artifacts(artifacts_base)

    save({
        ...
        "artifacts": art_paths,
        "project_name": project_name,
        ...
    })
```

- [ ] **Step 2: `cmd_update()` 也需更新 `artifacts` 欄位（繼承現有值，不要覆蓋）**

`cmd_update()` 保持現有邏輯，只在 `cmd_init()` 設定一次。

- [ ] **Step 3: 驗證**

```bash
cd /Users/tigerclaw/claude/skills/agent-workflow
# 測試 cmd_init 輸出 artifacts 路徑
python3 lib/handoff.py "" handoff_test.json init "test_demand" "[]" "config.yaml" market-sentiment 2>/dev/null
python3 -c "import json; d=json.load(open('handoff_test.json')); print(d['artifacts'])"
# 預期：包含 projects/market-sentiment/artifacts/
rm -f handoff_test.json
```

---

## Task 3：app.py — Per-project Artifacts API

### 修改：app.py

- [ ] **Step 1: `ARTIFACTS_DIR` 改動態讀取**

```python
def get_artifacts_dir() -> str:
    """從 handoff.json 讀取 per-project artifacts 目錄"""
    handoff = load_handoff()
    artifacts_path = handoff.get("artifacts", {}).get("spec", "")
    if artifacts_path:
        return os.path.dirname(artifacts_path)
    # fallback：嘗試從 handoff.project_name 重建
    project_name = handoff.get("project_name", "default")
    return os.path.join(BASE_DIR, "projects", project_name, "artifacts")
```

- [ ] **Step 2: 更新 `list_artifacts()`**

```python
def list_artifacts() -> list[dict]:
    artifacts_dir = get_artifacts_dir()
    if not os.path.exists(artifacts_dir):
        return []
    ...
```

- [ ] **Step 3: 更新 `api_artifact(filename)`**

使用 `get_artifacts_dir()` 而非全域 `ARTIFACTS_DIR`。

- [ ] **Step 4: 驗證**

```bash
cd /Users/tigerclaw/claude/skills/agent-workflow
python3 -c "
import app, os
os.chdir('/Users/tigerclaw/claude/skills/agent-workflow')
app.app.config['TESTING'] = True
with app.app.test_client() as c:
    r = c.get('/api/artifacts')
    print(r.get_json())
"
# 預期：回傳 Market_Sentiment 專案的 artifacts（不是舊的 minimax-image-server）
```

---

## Task 4：workflow_ui.html — 前端顯示 Per-project Artifacts

### 修改：templates/workflow_ui.html

- [ ] **Step 1: 更新 `loadArtifacts()` — 讀取動態 artifacts 路徑**

從 Pipeline Tab 可見 `data.project_name`，前端 `loadArtifacts()` 需使用專案名稱呼叫 `/api/artifacts`。

```javascript
// 現有 loadArtifacts() 呼叫 /api/artifacts
// 已正確（後端 get_artifacts_dir() 處理動態路徑）
// 無需改動 JS，只要後端正確即可
```

- [ ] **Step 2: 可選：在 Pipeline Tab 顯示當前專案名稱**

在 panel header 顯示 `data.project_name` 或 `data.project_root`（從 `/api/pipeline` 取得）。

- [ ] **Step 3: 驗證**

瀏覽器開啟 `workflow_ui.html`，切到 Pipeline Tab，確認 artifacts 清單是 Market_Sentiment 專案的內容。

---

## Task 5：寫測試

### 修改：tests/test_pipeline_api.py

- [ ] **Step 1: 寫失敗測試**

```python
def test_artifacts_per_project(monkeypatch, tmp_path):
    """同一 workflow dir，不同專案有獨立 artifacts"""
    # 建立 two projects
    proj_a = tmp_path / "projects" / "proj-a" / "artifacts"
    proj_b = tmp_path / "projects" / "proj-b" / "artifacts"
    proj_a.mkdir(parents=True)
    proj_b.mkdir(parents=True)
    # 寫入不同 SPEC.md
    (proj_a / "SPEC.md").write_text("SPEC for proj-a")
    (proj_b / "SPEC.md").write_text("SPEC for proj-b")

    # handoff.json 指向 proj-a
    handoff = tmp_path / "handoff.json"
    handoff.write_text(json.dumps({
        "project_name": "proj-a",
        "artifacts": {"spec": str(proj_a / "SPEC.md")}
    }))

    # list_artifacts() 應只看到 proj-a 的檔案
    import app as app_module
    monkeypatch.setattr(app_module, "HANDOFF", str(handoff))
    artifacts = app_module.list_artifacts()
    assert len(artifacts) == 1
    assert artifacts[0]["name"] == "SPEC.md"
```

- [ ] **Step 2: 執行測試確認失敗**

```bash
cd /Users/tigerclaw/claude/skills/agent-workflow
pytest tests/test_pipeline_api.py::test_artifacts_per_project -v
# 預期：FAIL（app.py 目前用固定路徑）
```

- [ ] **Step 3: 實作 `get_artifacts_dir()` 通過測試**

---

## Task 6：遷移現有 artifacts（可選，略過）

> 不迁移现有 artifacts，保持向后兼容。

現有 `shared-context/artifacts/` 保留不動。`app.py` 的 `get_artifacts_dir()` fallback 邏輯會先找 `handoff.json` 中的動態路徑，若無則 fallback 回 `shared-context/artifacts/`（舊 workflow）。

---

## 驗收標準

1. 新 pipeline 使用 `projects/{name}/artifacts/` 結構
2. `/api/artifacts` 回傳正確專案的檔案列表
3. 舊 workflow（無 `project_name` 欄位）仍能正常運作（fallback）
4. 所有現有 pytest 測試仍然通過
5. Pipeline Tab UI 正常顯示
