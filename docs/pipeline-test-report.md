# Pipeline Bug 報告 — Market_Sentiment 測試

**日期：** 2026-04-19
**測試主題：** Market_Sentiment 市場情緒分析工具
**Pipeline：** analyzer → backend-dev → frontend-dev → tester → deployer

---

## 🔴 Bug 1：Pipeline 卡在 Analyzer 等待用戶輸入

**現象：** analyzer Agent 完成後，停在「需要你協助的兩件事」等待輸入，pipeline 不會自動繼續執行下一個 agent。

**根因：** `runner.sh` 的 `run_agent()` 呼叫 `claude --print` 時，Agent 可能會提問（NEEDS_CONTEXT），此時 pipeline 無法自動繼續。

**影響：** Pipeline 無法真正全自動執行，停在需要人工介入的環節。

**建議修復：** Agent 提問時，pipeline 應記錄狀態並退出，讓用戶在 UI 決定是否繼續或提供答案。

---

## 🔴 Bug 2：`status` 永遠是 `in_progress`，從不變 `completed`

**現象：** `handoff.json` 中 `status` 欄位永遠是 `"in_progress"`，即使 `cmd_complete()` 被呼叫過。

**根因：** `handoff.py` 的 `cmd_update()` 固定寫入 `"status": "in_progress"`（第 79 行），覆蓋了 `cmd_complete()` 設定的 `"completed"`。

```python
# handoff.py:71-82
data.update({
    "round": round_n,
    "current_agent": agent,
    ...
    "status": "in_progress",  # ← 每次 update 都強制變 in_progress
})
```

**修復方案：** `cmd_update()` 不應覆蓋 `status`，只保留 `completed` 狀態：
```python
# 改為
if data.get("status") != "completed":
    data["status"] = "in_progress"
```

---

## 🔴 Bug 3（已確認）：Agent 無法寫入 `project_root`（Market_Sentiment 為空）

**現象：** `Market_Sentiment` 目錄完全空白（0 個原始碼），backend-dev 無法在 `project_root` 建立檔案。

**根因確認（Market_Sentiment Pipeline 實測）：**

backend-dev 說：
> 「由於沒有 `/Users/tigerclaw/code/Market_Sentiment/` 的寫入許可權，後端程式碼存放於 artifacts 目錄，需手動複製。」

Agent 實際行為：
1. `claude --print --agent backend-dev` 的工作目錄是 `PROJECT_ROOT`
2. Agent 執行 `mkdir -p` 和 `touch` 等命令，但這些變更存在於**子 shell 行程的生命週期內**
3. `claude --print` 行程結束後，所有工作目錄的變更隨即消失
4. Agent 改為將程式碼寫入 `shared-context/artifacts/backend-reference/`（相對路徑可以跨行程存活）

**驗證：** `shared-context/artifacts/` 確實有 `backend-reference/` 目錄。

**修復方向（已實作）：**
方案 B 實作：`run_agent()` 中用 subshell `cd "$PROJECT_ROOT" && claude --print`，確保 Agent 的 bash 工具 cwd 為 `PROJECT_ROOT`。

**實際驗證：** Agent 在 `$PROJECT_ROOT` 成功建立 `hello.txt` 並持久化。

**其他配套修復：**
- `init_dirs()`：確保 `PROJECT_ROOT` 目錄存在
- `ensure_remote()`：新專案自動 `git init` 並建立初始 commit



1. `load_config()` 讀 `config.market-sentiment.yaml` 中的 `project_root`
2. 但 YAML 解析可能失敗（Python yaml.safe_load 路徑問題）
3. 導致 `PROJECT_ROOT` 為空，Agent 不知道去哪裡寫檔案

**驗證方式：**
```bash
cd /Users/tigerclaw/claude/skills/agent-workflow
python3 -c "
import yaml
with open('config.market-sentiment.yaml') as f:
    cfg = yaml.safe_load(f)
print('project_root:', cfg.get('project_root', 'MISSING'))
"
```

**觀察：** 從 runner.sh 輸出可見 `PROJECT_ROOT: /Users/tigerclaw/code/Market_Sentiment` 是正確的，代表 YAML 解析成功。

**真正原因：** `claude --print` 呼叫時，Agent 的工作目錄是 `PROJECT_ROOT`，但 Agent 可能沒有正確地在該目錄建立檔案，而是寫到了 `shared-context/artifacts/`。

**建議修復：** Agent prompt 需更明確強調「實作類程式碼寫入 `{project_root}`」，並在 `handoff_footer` 中明確標示。

---

## 🟡 Bug 4：SPEC.md 被舊內容覆蓋

**現象：** `SPEC.md`（2026-04-18 09:07）內容仍是 `minimax-image-server`，被新的 Market_Sentiment SPEC.md 覆蓋。

**影響：** 歷史 SPEC.md 喪失。`shared-context/artifacts/` 只能容納一個專案的 artifacts，無法同時管理多個專案工作流。

**建議修復：** `shared-context/artifacts/` 應改為 `{WORKFLOW_DIR}/projects/{project_name}/artifacts/`，每個專案有獨立目錄。

---

## ✅ Bug 5：`log.md` Per-Project 隔離

**現象：** log.md 顯示 `## 2026-04-18 09:09` 完成，但 pipeline 實際是 `## 2026-04-19` 執行。

**根因：** `log.md` 保留了上一個 pipeline（minimax-image-server）的歷史記錄，沒有清除也沒有區分專案。

**修復方案：** `LOG_FILE` 改為 `${WORKFLOW_DIR}/projects/${PROJECT_NAME}/log.md`，與 `ARTIFACTS_DIR` 同結構。

**驗證：** Market_Sentiment pipeline 的 log 現在寫入 `projects/market-sentiment/log.md`。

---

## 🟡 Bug 6：`completed_agent` 陣列解析方式不一致

**現象：** `runner.sh` 中同時存在兩種 `completed_agent` 讀取方式：
- `python3 lib/handoff.py get completed_agent`（JSON 格式回傳）
- `jq -r '.completed_agent // [] ...'`（直接讀 JSON 檔）

**風險：** 兩種方式對空值/null 的處理不同，可能造成邏輯不一致。

---

## 修復優先順序

| 優先 | Bug | 嚴重性 | 修補複雜度 |
|------|-----|--------|-----------|
| P1 | Bug 2：status 永遠 in_progress | ✅ 已修 | 低 |
| P2 | Bug 1：Agent 提問時 pipeline 卡住 | ✅ 已修 | 中 |
| P3 | Bug 3：程式碼寫錯目錄 | ✅ 已修 | 中（subshell cd 解決） |
| P4 | Bug 4：多專案 artifacts 衝突 | ✅ 已修 | 中 |
| P5 | Bug 5：log 專案混淆 | ✅ 已修 | 低 |
| P6 | Bug 6：completed_agent 解析不一致 | ✅ 已修 | 低 |
