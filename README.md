# Agent Workflow — 公版工作流

串接 analyzer → backend-dev → frontend-dev → tester → deployer 五個 Agent 接力實作專案，以 Git commit 為快照點，中斷可復原。

---

## 目錄結構

```
skills/agent-workflow/
├── runner.sh              # 主腳本（start/resume/status/run）
├── compact.sh             # 每 5 輪自動壓縮 log
├── handoff.json          # 交接狀態（Git 可追蹤）
├── log.md                # 進度日誌
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

# 查看進度
./runner.sh status

# 從中斷點繼續
./runner.sh resume

# 執行單一 Agent
./runner.sh run backend-dev

# 單獨跑某個 Agent（可指定額外提示）
./runner.sh run tester "針對 /api/orders 補測試"
```

---

## 工作流程

```
[start] → analyzer → commit → handoff.json
    → backend-dev → commit → handoff.json
    → frontend-dev → commit → handoff.json
    → tester → commit → handoff.json
    → deployer → push → handoff.json → [完成]
```

每輪 Agent 必須：
1. 將產出寫入 `shared-context/artifacts/` 對應檔案
2. 更新 `handoff.json`（round、current_agent、next_agent、focus_for_next）
3. 在專案目錄執行 `git add + commit`

---

## 中斷復原邏輯

1. `resume` 讀取 `handoff.json` 的 `current_agent` + `round`
2. 依 `current_agent` 判斷從哪個 Agent 繼續
3. `status` 可隨時查看 git commit 歷史與 handoff 狀態

---

## 上下文控制策略

| 策略 | 做法 |
|------|------|
| 隔離歷史 | Agent 只讀 `handoff.json` + 目標 Artifact，不讀對話 transcript |
| 固定格式 | `handoff.json` 結構固定，隨時可截斷覆寫 |
| 快照壓縮 | 每 5 輪觸發 `compact.sh` 壓縮 log.md |
| Token 節費 | `handoff.json` 每次標記 `context_tokens_estimate`，超標時觸發 compact |

---

## 實例：點餐系統

以 [skytiger111/order-system](https://github.com/skytiger111/order-system) 為實作範本，綁定至 `~/code/order-system`。

每次工作流產出的 commit：
```
chore: analyzer 完成需求分析
feat: backend-dev 完成後端實作
feat: frontend-dev 完成前端實作
test: tester 完成測試撰寫
deploy: 完成部署
```

**修改綁定專案**：
```bash
export PROJECT_ROOT=/path/to/your/project
```

---
Developed with 🐯 by 標虎團隊 | 技術總監: 匠 (Coder Agent)
