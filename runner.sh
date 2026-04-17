#!/bin/bash
#===============================================
# Agent Workflow Runner — 點餐系統實例
# 串接 analyzer → backend-dev → frontend-dev → tester → deployer
# 中斷後可從 handoff.json 記錄點繼續
#===============================================

set -e

# 預設指向 order-system 專案（可透過環境變數覆寫）
PROJECT_ROOT="${PROJECT_ROOT:-/Users/tigerclaw/code/order-system}"
WORKFLOW_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTEXT_DIR="$WORKFLOW_DIR/shared-context"
LOG_FILE="$WORKFLOW_DIR/log.md"
HANDOFF="$WORKFLOW_DIR/handoff.json"
GIT_REMOTE="https://github.com/skytiger111/order-system.git"

AGENTS=("analyzer" "backend-dev" "frontend-dev" "tester" "deployer")

#------------------------------------------
# 工具函式
#------------------------------------------
info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*" >&2; }
error() { echo "[ERROR] $*" >&2; exit 1; }

#------------------------------------------
# 確保在專案目錄
#------------------------------------------
cd_project() { cd "$PROJECT_ROOT" || error "無法進入專案目錄: $PROJECT_ROOT"; }

#------------------------------------------
# 初始化目錄結構
#------------------------------------------
init_dirs() {
  mkdir -p "$CONTEXT_DIR/artifacts"
  if [[ ! -f "$LOG_FILE" ]]; then
    cat > "$LOG_FILE" << 'EOF'
# Workflow Log — 點餐系統
EOF
  fi
  if [[ ! -f "$HANDOFF" ]]; then
    echo '{}' > "$HANDOFF"
  fi
}

#------------------------------------------
# 讀取 handoff 欄位
#------------------------------------------
get_handoff() {
  local key="$1"
  local default="${2:-}"
  jq -r ".$key // \"$default\"" "$HANDOFF" 2>/dev/null || echo "$default"
}

#------------------------------------------
# 讀取 completed_agent 陣列
#------------------------------------------
get_completed() {
  jq -r '.completed_agent // [] | if type == "array" then .[] else empty end' "$HANDOFF" 2>/dev/null
}

#------------------------------------------
# 寫入 handoff（完整重建）
#------------------------------------------
write_handoff() {
  local round="$1"
  local agent="$2"
  local next="$3"
  local outputs="$4"
  local focus="$5"

  # 收集已完成的 agent 列表
  local completed_list
  completed_list=$(get_completed)
  [[ -n "$completed_list" ]] && completed_list=$(echo "$completed_list" | jq -R . | jq -s .)

  cat > "$HANDOFF" << EOF
{
  "round": $round,
  "current_agent": "$agent",
  "next_agent": "$next",
  "completed_agent": $(get_completed; echo "$agent" | jq -R . | jq -s '(. // []) + [.]'),
  "user_demand": "$(get_handoff 'user_demand' '')",
  "last_outputs": ["$outputs"],
  "focus_for_next": "$focus",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "in_progress",
  "artifacts": {
    "spec": "$CONTEXT_DIR/artifacts/SPEC.md",
    "api_contract": "$CONTEXT_DIR/artifacts/api-contract.md",
    "frontend_spec": "$CONTEXT_DIR/artifacts/component-spec.md",
    "test_report": "$CONTEXT_DIR/artifacts/test-report.md",
    "deploy_status": "$CONTEXT_DIR/artifacts/deploy-status.md"
  }
}
EOF
  info "handoff.json 更新 → $agent → $next"
}

#------------------------------------------
# git commit（快照點）
#------------------------------------------
workflow_commit() {
  local msg="$1"
  cd_project
  if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    git add -A
    git commit -m "$msg" --allow-empty 2>/dev/null || true
    local hash
    hash=$(git rev-parse --short HEAD 2>/dev/null)
    info "已 commit [$hash]: $msg"
    return 0
  else
    info "無變更，跳過 commit"
    return 1
  fi
}

#------------------------------------------
# 執行單一 Agent（subagent）
#------------------------------------------
run_agent() {
  local agent_name="$1"
  local task="${2:-}"
  local focus
  focus=$(get_handoff "focus_for_next" "")

  info "執行 Agent: $agent_name"
  [[ -n "$focus" ]] && info "囑託: $focus"

  cd_project

  # 建構給 Agent 的 prompt
  local agent_prompt="【工作流囑託】
上輪囑託: $focus

【你的任務】
$task

【重要】
完成後：
1. 將產出寫入 $CONTEXT_DIR/artifacts/ 對應檔案
2. 更新 $HANDOFF（round、current_agent、next_agent、last_outputs、focus_for_next）
3. 在 $PROJECT_ROOT 執行 git add + commit"

  # 呼叫 Claude Code，切換 Agent
  claude --agent "$agent_name" --print "$agent_prompt"
}

#------------------------------------------
# 追加 log
#------------------------------------------
append_log() {
  local agent="$1"
  local status="$2"
  local note="${3:-}"

  cat >> "$LOG_FILE" << EOF

## $(date '+%Y-%m-%d %H:%M')

**Agent:** $agent
**Status:** $status
**Note:** $note
EOF
}

#------------------------------------------
# 確認 git remote 正確
#------------------------------------------
ensure_remote() {
  cd_project
  local remote
  remote=$(git remote get-url origin 2>/dev/null || echo "")
  if [[ -z "$remote" ]]; then
    info "設定 remote origin..."
    git remote add origin "$GIT_REMOTE" 2>/dev/null || git remote set-url origin "$GIT_REMOTE"
  fi
}

#------------------------------------------
# 完整工作流
#------------------------------------------
cmd_start() {
  local user_demand="${1:-}"
  [[ -z "$user_demand" ]] && error "請提供需求：./runner.sh start \"你的需求\""

  init_dirs
  ensure_remote

  # 寫入初始 handoff
  cat > "$HANDOFF" << EOF
{
  "round": 0,
  "current_agent": null,
  "next_agent": "analyzer",
  "completed_agent": [],
  "user_demand": "$user_demand",
  "last_outputs": [],
  "focus_for_next": "分析需求，產出 SPEC.md",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "in_progress",
  "artifacts": {
    "spec": "$CONTEXT_DIR/artifacts/SPEC.md",
    "api_contract": "$CONTEXT_DIR/artifacts/api-contract.md",
    "frontend_spec": "$CONTEXT_DIR/artifacts/component-spec.md",
    "test_report": "$CONTEXT_DIR/artifacts/test-report.md",
    "deploy_status": "$CONTEXT_DIR/artifacts/deploy-status.md"
  }
}
EOF

  info "=========================================="
  info "工作流啟動 — 點餐系統"
  info "需求: $user_demand"
  info "=========================================="

  #--- Round 1: Analyzer ---
  info "========== Round 1: Analyzer =========="
  run_agent "analyzer" "需求：$user_demand

現有專案結構（供參考）：
$(ls "$PROJECT_ROOT")

現有後端：$PROJECT_ROOT/app.py（Flask，資料庫：SQLite）

請產出 $CONTEXT_DIR/artifacts/SPEC.md，包含：
- 功能範圍與 YAGNI 邊界
- API 端點（request/response 格式）
- 資料庫 schema（如有變更）
- 異常處理對應 HTTP 狀態碼"

  workflow_commit "chore: analyzer 完成需求分析"
  write_handoff 1 "analyzer" "backend-dev" \
    "$CONTEXT_DIR/artifacts/SPEC.md" \
    "依據 SPEC.md 實作後端 API（Flask routes）"

  append_log "analyzer" "完成"

  #--- Round 2: Backend ---
  info "========== Round 2: Backend-Dev =========="
  run_agent "backend-dev" "依據 SPEC.md 實作後端 API

現有後端入口：$PROJECT_ROOT/app.py
資料庫工具：$PROJECT_ROOT/database.py
設定檔：$PROJECT_ROOT/config.py
現有路由（請勿破壞）：
- /api/menu GET
- /api/orders POST, GET <id>
- /api/admin/orders GET, PUT <id>/status
- /admin/login GET, POST
- /api/reports/daily GET
- /api/checkout POST

請在 $CONTEXT_DIR/artifacts/api-contract.md 補上 API 合約，並實作功能。"

  workflow_commit "feat: backend-dev 完成後端實作"
  write_handoff 2 "backend-dev" "frontend-dev" \
    "app.py, database.py, config.py" \
    "依據 API 合約實作前端（HTML/CSS/JS）"

  append_log "backend-dev" "完成"

  #--- Round 3: Frontend ---
  info "========== Round 3: Frontend-Dev =========="
  run_agent "frontend-dev" "依據 SPEC.md 和 api-contract.md 實作前端

現有模板：$PROJECT_ROOT/templates/
現有靜態檔：$PROJECT_ROOT/static/
現有後端 API 請見 $CONTEXT_DIR/artifacts/api-contract.md

需實作或更新：
- templates/index.html（首頁）
- templates/order.html（點餐頁）
- templates/admin.html（後台）
- 對應 static/css/*.css

響應式斷點：桌面 >768px / 手機 ≤768px"

  workflow_commit "feat: frontend-dev 完成前端實作"
  write_handoff 3 "frontend-dev" "tester" \
    "templates/, static/" \
    "為核心功能撰寫單元測試與整合測試"

  append_log "frontend-dev" "完成"

  #--- Round 4: Tester ---
  info "========== Round 4: Tester =========="
  run_agent "tester" "為點餐系統撰寫測試

SPEC.md：$CONTEXT_DIR/artifacts/SPEC.md
後端入口：$PROJECT_ROOT/app.py

測試框架：pytest
測試目標：
- API 端點（/api/menu、/api/orders、/api/admin/*）
- 訂單建立流程
- 庫存/狀態更新
- 錯誤情境（404、503、逾時）

測試檔放在 $PROJECT_ROOT/tests/（對應 app/ 目錄結構）
Mock 外部 API 以確保測試穩定"

  workflow_commit "test: tester 完成測試撰寫"
  write_handoff 4 "tester" "deployer" \
    "tests/" \
    "整理程式碼，推送到 GitHub"

  append_log "tester" "完成"

  #--- Round 5: Deployer ---
  info "========== Round 5: Deployer =========="
  run_agent "deployer" "將點餐系統程式碼推送至 GitHub

專案根目錄：$PROJECT_ROOT
Remote：$GIT_REMOTE
預設分支：main

工作：
1. 確認所有檔案已 commit（git status）
2. git push origin main
3. 如需初始化 git repo，先 git init 並建立第一個 commit
4. 更新 $CONTEXT_DIR/artifacts/deploy-status.md（部署狀態）"

  workflow_commit "deploy: 完成部署"
  write_handoff 5 "deployer" "" \
    "" \
    "工作流完成"

  # 最終狀態
  cat > "$HANDOFF" << 'EOF'
{
  "status": "completed",
  "completed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

  append_log "deployer" "完成" "已推送至 GitHub"

  info "=========================================="
  info "工作流完成！"
  info "查看 log: cat $LOG_FILE"
  info "=========================================="
}

#------------------------------------------
# 從中斷點繼續
#------------------------------------------
cmd_resume() {
  init_dirs

  local current
  current=$(get_handoff "current_agent" "")
  local status
  status=$(get_handoff "status" "unknown")
  local round
  round=$(get_handoff "round" "0")

  [[ "$status" == "completed" ]] && info "工作流已完成" && return 0
  [[ -z "$current" || "$current" == "null" ]] && error "無中斷記錄，請用 start 啟動"

  info "=========================================="
  info "從中斷點繼續 — current_agent: $current"
  info "round: $round，status: $status"
  info "=========================================="

  local user_demand
  user_demand=$(get_handoff "user_demand" "")

  case "$current" in
    analyzer)
      cmd_start "$user_demand" ;;
    backend-dev)
      info "從 Backend-Dev 繼續（R2 實作）" ;;
    frontend-dev)
      info "從 Frontend-Dev 繼續（R3 實作）" ;;
    tester)
      info "從 Tester 繼續（R4 測試）" ;;
    deployer)
      info "從 Deployer 繼續（R5 部署）" ;;
    *)
      error "未知的 current_agent: $current" ;;
  esac
}

#------------------------------------------
# 查看狀態
#------------------------------------------
cmd_status() {
  init_dirs
  echo ""
  echo "========== 工作流狀態 =========="
  echo ""
  if [[ -f "$HANDOFF" ]]; then
    echo "--- handoff.json ---"
    cat "$HANDOFF"
    echo ""
  fi
  echo "--- git log (最近 5 筆) ---"
  cd_project
  git log --oneline -5 2>/dev/null || echo "(非 git 專案或無 commit)"
  echo ""
  echo "--- completed_agent ---"
  get_completed | sed 's/^/  /'
  echo "=============================="
}

#------------------------------------------
# 執行單一 Agent
#------------------------------------------
cmd_run() {
  local agent="${1:-}"
  shift
  init_dirs
  [[ -z "$agent" ]] && error "用法: $0 run <agent> [task]"

  cd_project
  claude --agent "$agent" --print "$*"
}

#------------------------------------------
# 入口
#------------------------------------------
COMMAND="${1:-help}"
shift || true

case "$COMMAND" in
  start)  cmd_start "$@" ;;
  resume) cmd_resume "$@" ;;
  status) cmd_status "$@" ;;
  run)    cmd_run "$@" ;;
  *)      cat << EOF
用法:
  $0 start  "需求描述"   啟動完整工作流
  $0 resume                  從中斷點繼續
  $0 status                  查看狀態
  $0 run <agent> [task]      執行單一 Agent

可用 Agent: ${AGENTS[*]}

範例:
  $0 start "新增會員點數功能"
  $0 status
EOF
      ;;
esac
