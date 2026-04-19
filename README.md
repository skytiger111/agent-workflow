## 更新紀錄
- 2026-04-19 — fix: Bug 3 — run_agent() 在 PROJECT_ROOT subshell 執行，確保 Agent 檔案寫入正確目錄；init_dirs/ensure_remote 新增新專案初始化（git init + 初始 commit）
- 2026-04-19 — fix: Pipeline 三大 bug — status 狀態保護 / completed_agent JSON 解析 / Agent 提問偵測並暫停 pipeline
- 2026-04-19 — chore: Pipeline Tab 整合驗證完成（Flask 啟動正常、API 回傳正確、UI 渲染正確）
- 2026-04-19 — feat: 新增 Pipeline Tab，含節點圖（done/running/pending 三態 + pulse 動畫）、詳情面板、commit 歷史，每 5 秒自動刷新
- 2026-04-19 — feat: 新增 /api/pipeline 端點含 4 情境 TDD 測試（normal/empty/completed/custom agents）
- 2026-04-19 — fix: 修補測試覆蓋缺口（mixed_status 情境、commits/round assert、completed_agent 型別保護）

---

# Agent Workflow — 公版工作流

串接多個 Agent 接力實作專案，以 Git commit 為快照點，中斷可復原。

---

## 目錄結構

```
skills/agent-workflow/
├── runner.sh                  # 主腳本（start/resume/status/run）
├── compact.sh                 # 每 5 輪自動壓縮 log
├── config.yaml                # 工作流設定（可複製自訂）
├── config.generic.yaml        # 通用預設設定
├── handoff.json              # 交接狀態（Git 可追蹤）
├── log.md                     # 進度日誌
└── shared-context/
    └── artifacts/
        ├── SPEC.md              # 規格文件（analyzer 產出）
        ├── api-contract.md      # API 合約（backend-dev 產出）
        ├── component-spec.md    # 前端元件規格（frontend-dev 產出）
        ├── test-report.md       # 測試報告（tester 產出）
        └── deploy-status.md     # 部署狀態（deployer 產出）
```

---

## 使用方式

```bash
cd ~/claude/skills/agent-workflow

# 啟動新專案
./runner.sh start "需求描述"

# 自訂設定檔（複製並修改 config.yaml）
./runner.sh start "需求描述" config.myproject.yaml

# 查看進度
./runner.sh status

# 從中斷點繼續（真正可用的 resume）
./runner.sh resume

# 執行單一 Agent
./runner.sh run backend-dev

# 單獨跑某個 Agent（可指定額外提示）
./runner.sh run tester "針對 /api/orders 補測試"
```

---

## 工作流程

```
[start] → agent₁ → commit → handoff.json
       → agent₂ → commit → handoff.json
       → agent₃ → commit → handoff.json
       → ...
       → deployer → push → handoff.json → [完成]
```

每輪 Agent 必須：
1. 將產出寫入 `shared-context/artifacts/` 對應檔案
2. 更新 `handoff.json`（round、current_agent、next_agent、focus_for_next）
3. 在專案目錄執行 `git add + commit`

---

## 中斷復原邏輯（已實作）

1. `resume` 讀取 `handoff.json` 的 `current_agent` + `round`
2. 找出 `current_agent` 在 Agent 列表中的索引
3. 從該索引繼續執行所有剩餘 Agent
4. 已完成的 Agent 自動略過

---

## 自訂工作流（config.yaml）

複製 `config.yaml` 或 `config.generic.yaml` 為新設定檔，自由定義：

```yaml
name: "my-project-workflow"
version: "1.0"
project_root: "/path/to/my/project"
git_remote: "https://github.com/user/repo.git"
git_branch: "main"

agents:
  - name: planner
    description: "規劃實作步驟"
    prompt_template: |
      分析需求：{user_demand}
      產出 {artifacts_dir}/plan.md
    artifacts:
      - "{artifacts_dir}/plan.md"
    commit_message: "chore: planner 完成實作規劃"

  - name: backend-dev
    description: "後端實作"
    prompt_template: |
      依據 plan.md 實作後端：{project_root}
    artifacts:
      - "{artifacts_dir}/api-contract.md"
    commit_message: "feat: backend-dev 完成後端實作"
```

### 模板變數

| 變數 | 說明 |
|------|------|
| `{user_demand}` | 啟動時的需求描述 |
| `{project_root}` | 專案根目錄 |
| `{artifacts_dir}` | artifacts 目錄 |
| `{handoff_file}` | handoff.json 檔案路徑 |
| `{git_remote}` | Git remote URL |
| `{git_branch}` | Git 分支名稱 |
| `{project_files}` | 專案檔案列表（前 40 個） |

---

## 上下文控制策略

| 策略 | 做法 |
|------|------|
| 隔離歷史 | Agent 只讀 `handoff.json` + 目標 Artifact，不讀對話 transcript |
| 固定格式 | `handoff.json` 結構固定，隨時可截斷覆寫 |
| 快照壓縮 | 每 5 輪觸發 `compact.sh` 壓縮 log.md |
| Token 節費 | `handoff.json` 每次標記 `context_tokens_estimate`，超標時觸發 compact |
| 通用化 | `config.yaml` 可自訂 Agent 數量、順序、prompt 模板 |

---

## 實例：點餐系統

以 [skytiger111/order-system](https://github.com/skytiger111/order-system) 為實作範本，綁定至 `~/code/order-system`。

每次工作流產出的 commit：
```
chore: planner 完成實作規劃
feat: backend-dev 完成後端實作
feat: frontend-dev 完成前端實作
test: tester 完成測試撰寫
deploy: 完成部署
```

---

Developed with 🐯 by 標虎團隊 | 技術總監: 匠 (Coder Agent)
