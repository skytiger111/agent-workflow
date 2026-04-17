# Agent 工作流 — 交接提示範本

## 設計原則

- 每個 Agent 只讀取 `handoff.json` + 自己需要的 Artifact
- **不繼承對話歷史**，只繼承結構化產出
- 每次交接強制寫入 `handoff.json` + commit，確保中斷可復原

## handoff.json 格式

```json
{
  "round": 3,
  "current_agent": "frontend-dev",
  "next_agent": "tester",
  "completed_agent": "frontend-dev",
  "user_demand": "天氣查詢 API + 響應式前端",
  "last_outputs": ["static/js/main.js", "templates/index.html"],
  "focus_for_next": "為 /api/weather 撰寫單元測試與整合測試",
  "artifacts": {
    "spec": "docs/SPEC.md",
    "api_contract": "docs/api-contract.md",
    "frontend_spec": "docs/component-spec.md",
    "test_report": "docs/test-report.md",
    "deploy_status": "docs/deploy-status.md"
  },
  "timestamp": "2026-04-17T10:30:00Z",
  "status": "ready",
  "git_commits": [
    { "round": 1, "msg": "chore: analyzer 完成需求分析", "hash": "abc123" },
    { "round": 2, "msg": "feat: backend-dev 完成後端實作", "hash": "def456" }
  ]
}
```

## 交接檢查清單（每輪必做）

- [ ] 產出目標 Artifact
- [ ] 更新 `handoff.json`（round、current_agent、next_agent、last_outputs、focus_for_next）
- [ ] `git add -A && git commit`
- [ ] `git log --oneline -1` 確認 commit 成功
- [ ] append 到 `log.md`

## 上下文控制策略

| 策略 | 做法 |
|------|------|
| 隔離歷史 | Agent 只讀 `handoff.json` + 目標 Artifact，不讀對話 transcript |
| 固定格式 | `handoff.json` 結構固定，隨時可截斷或覆寫 |
| 快照壓縮 | 每 5 輪做一次 `log-summary.md`，壓縮歷史 |
| 增量產出 | 每個 Artifact 獨立檔案，內容變更才更新 |
| Token 估算 | `handoff.json` 每次標記 `context_tokens_estimate`，超標時觸發 compact |

## 每輪 Agent 的系統提示（附加到 Agent prompt）

```
你正在執行工作流 round {N}。
上輪完成者：{prev_agent}
你的任務：{focus_for_next}
重要：完成後更新 shared-context/handoff.json 並 commit。
```
