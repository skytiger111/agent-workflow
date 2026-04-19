#!/bin/bash
#===============================================
# Agent Workflow Runner — 重構版
# 支援 config.yaml 自訂工作流、真正可用的 resume、jq 寫入 JSON
#===============================================

set -euo pipefail

#------------------------------------------
# 預設值（可被 config.yaml 覆寫）
#------------------------------------------
WORKFLOW_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="${WORKFLOW_DIR}/config.yaml"
CONTEXT_DIR="${WORKFLOW_DIR}/shared-context"
ARTIFACTS_DIR="${CONTEXT_DIR}/artifacts"
LOG_FILE="${WORKFLOW_DIR}/log.md"
HANDOFF="${WORKFLOW_DIR}/handoff.json"
PROJECT_ROOT=""
GIT_REMOTE=""
GIT_BRANCH="main"
AGENTS=()
HANDSOFF_FOOTER=""

#------------------------------------------
# 工具函式
#------------------------------------------
info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*" >&2; }
error() { echo "[ERROR] $*" >&2; exit 1; }

#------------------------------------------
# 嘗試讀取 config.yaml
#------------------------------------------
load_config() {
  local cfg="${1:-${CONFIG_FILE}}"
  if [[ -f "$cfg" ]]; then
    CONFIG_FILE="$cfg"
    info "載入設定檔: $cfg"
  else
    warn "設定檔不存在: $cfg，使用預設值"
    return 1
  fi

  if command -v python3 &>/dev/null; then
    PROJECT_ROOT=$(python3 -c "
import yaml, sys
with open('$cfg') as f:
    cfg = yaml.safe_load(f)
print(cfg.get('project_root', ''))
" 2>/dev/null || echo "")

    GIT_REMOTE=$(python3 -c "
import yaml, sys
with open('$cfg') as f:
    cfg = yaml.safe_load(f)
print(cfg.get('git_remote', ''))
" 2>/dev/null || echo "")

    GIT_BRANCH=$(python3 -c "
import yaml, sys
with open('$cfg') as f:
    cfg = yaml.safe_load(f)
print(cfg.get('git_branch', 'main'))
" 2>/dev/null || echo "main")

    HANDSOFF_FOOTER=$(python3 -c "
import yaml, sys
with open('$cfg') as f:
    cfg = yaml.safe_load(f)
footer = cfg.get('handoff_footer', '')
print(footer)
" 2>/dev/null || echo "")
  else
    warn "python3 不可用，無法解析 YAML，請手動設定"
  fi
}

#------------------------------------------
# 初始化目錄結構
#------------------------------------------
init_dirs() {
  mkdir -p "$ARTIFACTS_DIR"
  [[ ! -f "$LOG_FILE" ]] && echo "# Workflow Log" > "$LOG_FILE"
  [[ ! -f "$HANDOFF" ]] && echo '{}' > "$HANDOFF"
  true
}

#------------------------------------------
# jq helper：讀取 JSON 欄位
#------------------------------------------
jq_get() {
  python3 "$WORKFLOW_DIR/lib/handoff.py" "$ARTIFACTS_DIR" "$HANDOFF" get "$1" "$2"
}


#------------------------------------------
# 更新 handoff（Python 確保 JSON 型別正確）
#------------------------------------------
write_handoff() {
  python3 "$WORKFLOW_DIR/lib/handoff.py" \
    "$ARTIFACTS_DIR" "$HANDOFF" update \
    "$1" "$2" "$3" "$4" "$5"
}

#------------------------------------------
# git commit（快照點）
#------------------------------------------
workflow_commit() {
  local msg="$1"
  if [[ ! -d "$PROJECT_ROOT" ]]; then
    warn "PROJECT_ROOT 不存在: $PROJECT_ROOT，跳過 commit"
    return 1
  fi
  (
    cd "$PROJECT_ROOT" || exit 1
    if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
      git add -A
      if git commit -m "$msg" --allow-empty 2>/dev/null; then
        local hash
        hash=$(git rev-parse --short HEAD 2>/dev/null)
        info "已 commit [$hash]: $msg"
        return 0
      else
        warn "git commit 失敗"
        return 1
      fi
    else
      info "無變更，跳過 commit"
      return 1
    fi
  )
}

#------------------------------------------
# 確認 git remote
#------------------------------------------
ensure_remote() {
  if [[ -z "$PROJECT_ROOT" ]] || [[ ! -d "$PROJECT_ROOT" ]]; then
    warn "PROJECT_ROOT 無效: $PROJECT_ROOT"
    return 1
  fi
  (
    cd "$PROJECT_ROOT" || exit 1
    if [[ -n "$GIT_REMOTE" ]]; then
      local remote
      remote=$(git remote get-url origin 2>/dev/null || echo "")
      if [[ -z "$remote" ]]; then
        info "設定 remote origin..."
        git remote add origin "$GIT_REMOTE" 2>/dev/null || git remote set-url origin "$GIT_REMOTE"
      fi
    fi
  )
}

#------------------------------------------
# 列出專案檔案
#------------------------------------------
list_project_files() {
  if [[ -d "$PROJECT_ROOT" ]]; then
    (cd "$PROJECT_ROOT" && find . -maxdepth 5 -type f \( -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.html" -o -name "*.css" -o -name "*.yaml" -o -name "*.yml" -o -name "*.json" -o -name "*.md" -o -name "*.sh" \) -not -path "./node_modules/*" -not -path "./.git/*" -not -path "./dist/*" -not -path "./build/*" | sort | head -80) 2>/dev/null || echo "(專案目錄為空或無法存取)"
  else
    echo "(專案目錄不存在: $PROJECT_ROOT)"
  fi
}

#------------------------------------------
# 替換 prompt 模板中的變數
#------------------------------------------
render_prompt() {
  python3 "$WORKFLOW_DIR/lib/render_prompt.py" "$1"
}

#------------------------------------------
# 執行單一 Agent
#------------------------------------------
run_agent() {
  local agent_name="$1"
  local task="$2"
  local focus="$3"
  local commit_msg="$4"

  info "=========================================="
  info "Agent: $agent_name"
  [[ -n "$focus" ]] && info "囑託: $focus"
  info "=========================================="

  # 將 config 變數 export 給 subagent（claude CLI 需看得見）
  export PROJECT_ROOT GIT_REMOTE GIT_BRANCH ARTIFACTS_DIR HANDOFF USER_DEMAND

  # 替換 prompt 模板中的變數（{user_demand}, {project_files} 等）
  local rendered_task
  rendered_task=$(render_prompt "$task")

  # bash 3.2 + set -u 會在 heredoc 內展開全域變數時出錯
  # 改用雙引號 heredoc（不展開變數）再串接
  local _prompt_body
  _prompt_body=$(cat <<'TPL'
【工作流囑託】
上輪囑託:

【你的任務】

【交接提示】
1. 將產出寫入  對應檔案
2. 更新 （round、current_agent、next_agent、last_outputs、focus_for_next）
3. 在  執行 git add + commit

【交接提示（來自 config）】
TPL
)
  local full_prompt="${_prompt_body}"
  full_prompt="${full_prompt}【工作流囑託】
上輪囑託: ${focus:-無}

【你的任務】
${rendered_task}

【交接提示】
1. 將產出寫入 ${ARTIFACTS_DIR}/ 對應檔案
2. 更新 ${HANDOFF}（round、current_agent、next_agent、last_outputs、focus_for_next）
3. 在 ${PROJECT_ROOT} 執行 git add + commit

【交接提示（來自 config）】
${HANDSOFF_FOOTER:-}
"

  unset _prompt_body

  if command -v claude &>/dev/null; then
    # 捕獲輸出並偵測是否需要用戶輸入
    local output_file="${WORKFLOW_DIR}/.agent_output_$$.tmp"
    claude --print --agent "$agent_name" "$full_prompt" > "$output_file" 2>&1 || true

    # 偵測 Agent 是否在等待用戶輸入
    local needs_input=false
    if grep -qiE "需要你協助|請問|請確認|needs?.your|your.input|請提供以下|請回覆" "$output_file" 2>/dev/null; then
      needs_input=true
    fi

    # 輸出內容（只顯示前 50 行，避免佔據太多終端）
    if [[ -s "$output_file" ]]; then
      head -50 "$output_file"
      echo "..."
    fi
    rm -f "$output_file"

    if [[ "$needs_input" == true ]]; then
      # 回傳 exit code 10 表示需要用戶輸入
      return 10
    fi
  else
    error "claude CLI 未安裝，無法執行 Agent"
  fi
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
# 從 config.yaml 讀取 Agent 列表
#------------------------------------------
load_agents_from_config() {
  if [[ ! -f "$CONFIG_FILE" ]] || ! command -v python3 &>/dev/null; then
    return 1
  fi

  AGENTS=()
  local names
  names=$(python3 "$WORKFLOW_DIR/lib/load_agents.py" "$CONFIG_FILE") || return 1

  for name in $names; do
    [[ -n "$name" ]] && AGENTS+=("$name")
  done
}

#------------------------------------------
# 從 config.yaml 取得 Agent prompt
#------------------------------------------
get_agent_prompt() {
  local agent="$1"
  local user_demand="$2"

  if [[ -f "$CONFIG_FILE" ]] && command -v python3 &>/dev/null; then
    python3 "$WORKFLOW_DIR/lib/query_config.py" "$CONFIG_FILE" agent_prompt "$agent" 2>/dev/null && return
  fi

  echo "執行 $agent，需求：$user_demand"
}

#------------------------------------------
# 從 config.yaml 取得 Agent focus
#------------------------------------------
get_agent_focus() {
  local agent="$1"
  local next="$2"

  if [[ -f "$CONFIG_FILE" ]] && command -v python3 &>/dev/null; then
    python3 "$WORKFLOW_DIR/lib/query_config.py" "$CONFIG_FILE" agent_focus "$agent" 2>/dev/null && return
  fi

  echo "交接給下一個 Agent: $next"
}

#------------------------------------------
# 從 config.yaml 取得 Agent commit message
#------------------------------------------
get_agent_commit() {
  local agent="$1"

  if [[ -f "$CONFIG_FILE" ]] && command -v python3 &>/dev/null; then
    python3 "$WORKFLOW_DIR/lib/query_config.py" "$CONFIG_FILE" agent_commit "$agent" 2>/dev/null && return
  fi

  echo "chore: $agent 完成"
}

#------------------------------------------
# 完整工作流
#------------------------------------------
cmd_start() {
  local user_demand="${1:-}"
  [[ -z "$user_demand" ]] && error "請提供需求：./runner.sh start \"你的需求\""
  export USER_DEMAND="$user_demand"

  load_config "${2:-${CONFIG_FILE}}"
  load_agents_from_config

  if [[ ${#AGENTS[@]} -eq 0 ]]; then
    warn "無法從 config.yaml 讀取 Agent 列表，使用預設值"
    AGENTS=("analyzer" "backend-dev" "frontend-dev" "tester" "deployer")
    # 不再硬編碼路徑，agent 自 config.yaml 讀取 project_root
  fi

  init_dirs
  ensure_remote

  # 使用 Python 初始化 handoff
  local agents_json
  agents_json=$(printf '%s\n' "${AGENTS[@]}" | jq -R . | jq -s .)
  python3 "$WORKFLOW_DIR/lib/handoff.py" \
    "$ARTIFACTS_DIR" "$HANDOFF" init "$user_demand" "$agents_json"

  info "=========================================="
  info "工作流啟動"
  info "需求: $user_demand"
  info "Agent 數: ${#AGENTS[@]}"
  info "PROJECT_ROOT: $PROJECT_ROOT"
  info "=========================================="

  for i in "${!AGENTS[@]}"; do
    local agent="${AGENTS[$i]}"
    local next="${AGENTS[$((i + 1))]:-}"

    info "========== Round $((i+1)): $agent =========="

    local task focus commit_msg
    task=$(get_agent_prompt "$agent" "$user_demand")
    focus=$(get_agent_focus "$agent" "$next")
    commit_msg=$(get_agent_commit "$agent")

    # 只更新 current/next，不標記完成（成功後才標記）
    write_handoff $((i+1)) "$agent" "$next" "" "$focus"
    run_agent "$agent" "$task" "$focus" "$commit_msg"
    local exit_code=$?
    if [[ $exit_code -eq 10 ]]; then
      # Agent 需要用戶輸入，pipeline 暫停
      info "=========================================="
      info "⚠ Agent $agent 需要用戶輸入，pipeline 暫停"
      info "請在 UI 回應後執行 ./runner.sh resume 繼續"
      info "=========================================="
      append_log "$agent" "需要用戶輸入" "pipeline 暫停，請先回應後執行 resume"
      break
    elif [[ $exit_code -ne 0 ]]; then
      warn "Agent $agent 執行失敗"
      break
    fi
    # 執行成功後才標記為完成
    python3 "$WORKFLOW_DIR/lib/handoff.py" \
      "$ARTIFACTS_DIR" "$HANDOFF" update \
      $((i+1)) "$agent" "$next" "" "$focus" "true"
    workflow_commit "${commit_msg:-chore: $agent 完成}" || warn "Commit 失敗，將繼續"
    append_log "$agent" "完成" || true
  done

  python3 "$WORKFLOW_DIR/lib/handoff.py" \
    "$ARTIFACTS_DIR" "$HANDOFF" complete

  append_log "workflow" "完成" "所有 Agent 已執行完畢"

  info "=========================================="
  info "工作流完成！"
  info "查看 log: cat $LOG_FILE"
  info "=========================================="
}

#------------------------------------------
# 從中斷點繼續
#------------------------------------------
cmd_resume() {
  load_config "${2:-${CONFIG_FILE}}"
  load_agents_from_config

  if [[ ${#AGENTS[@]} -eq 0 ]]; then
    AGENTS=("analyzer" "backend-dev" "frontend-dev" "tester" "deployer")
    [[ -z "$PROJECT_ROOT" ]] && PROJECT_ROOT="/Users/tigerclaw/code/order-system"
  fi

  init_dirs

  local current status round user_demand
  current=$(jq_get "current_agent" "")
  status=$(jq_get "status" "unknown")
  round=$(jq_get "round" "0")
  user_demand=$(jq_get "user_demand" "")

  [[ "$status" == "completed" ]] && info "工作流已完成" && return 0
  [[ -z "$current" || "$current" == "null" ]] && error "無中斷記錄，請用 start 啟動"

  info "=========================================="
  info "從中斷點繼續"
  info "current_agent: $current (round $round)"
  info "status: $status"
  info "=========================================="

  local start_idx=-1
  for i in "${!AGENTS[@]}"; do
    if [[ "${AGENTS[$i]}" == "$current" ]]; then
      start_idx=$i
      break
    fi
  done

  [[ $start_idx -eq -1 ]] && error "current_agent '$current' 不在 agent_list 中"

  for i in "${!AGENTS[@]}"; do
    if [[ $i -lt $start_idx ]]; then
      info "略過（已執行）: ${AGENTS[$i]}"
      continue
    fi

    local agent="${AGENTS[$i]}"
    local next="${AGENTS[$((i + 1))]:-}"

    # 跳過已完成的 agent（防重複執行）- 使用 Python 解析 JSON 陣列
    if python3 -c "
import json,sys
with open('$HANDOFF') as f:
    h = json.load(f)
completed = h.get('completed_agent') or []
sys.exit(0 if '$agent' in completed else 1)
" 2>/dev/null; then
      info "略過已完成: $agent"
      continue
    fi

    info "========== 繼續 Round $((i+1)): $agent =========="

    local task focus commit_msg
    task=$(get_agent_prompt "$agent" "$user_demand")
    focus=$(get_agent_focus "$agent" "$next")
    commit_msg=$(get_agent_commit "$agent")

    write_handoff $((i+1)) "$agent" "$next" "" "$focus"
    run_agent "$agent" "$task" "$focus" "$commit_msg" || { warn "Agent $agent 執行失敗"; break; }
    python3 "$WORKFLOW_DIR/lib/handoff.py" \
      "$ARTIFACTS_DIR" "$HANDOFF" update \
      $((i+1)) "$agent" "$next" "" "$focus" "true"
    workflow_commit "${commit_msg:-chore: $agent 完成}" || warn "Commit 失敗，將繼續"
    append_log "$agent" "完成（resume）" || true
  done

  append_log "workflow" "完成（resume）" "從 $current 恢復"

  info "=========================================="
  info "工作流完成（從 resume 恢復）！"
  info "=========================================="
}

#------------------------------------------
# 查看狀態
#------------------------------------------
cmd_status() {
  load_config "${2:-${CONFIG_FILE}}"
  load_agents_from_config

  init_dirs
  echo ""
  echo "========== 工作流狀態 =========="
  echo ""
  echo "設定檔: ${CONFIG_FILE}"
  if [[ -f "$CONFIG_FILE" ]]; then
    echo "工作流名稱: $(python3 "$WORKFLOW_DIR/lib/query_config.py" "$CONFIG_FILE" name 2>/dev/null || echo "(未設定)")"
  fi
  echo "PROJECT_ROOT: ${PROJECT_ROOT:-未設定}"
  echo ""
  echo "--- handoff.json ---"
  [[ -f "$HANDOFF" ]] && cat "$HANDOFF"
  echo ""
  echo "--- Agent 列表 ---"
  if [[ ${#AGENTS[@]} -gt 0 ]]; then
    for a in "${AGENTS[@]}"; do echo "  - $a"; done
  else
    echo "  (從 config.yaml 讀取失敗)"
  fi
  echo ""
  echo "--- git log (最近 5 筆) ---"
  if [[ -n "$PROJECT_ROOT" ]] && [[ -d "$PROJECT_ROOT" ]]; then
    (cd "$PROJECT_ROOT" && git log --oneline -5 2>/dev/null) || echo "(非 git 專案或無 commit)"
  else
    echo "(PROJECT_ROOT 無效)"
  fi
  echo ""
  echo "--- completed_agent ---"
  local completed
  completed=$(jq -r '.completed_agent // [] | if type == "array" then .[] else empty end' "$HANDOFF" 2>/dev/null)
  [[ -z "$completed" ]] && echo "  (無)" || echo "$completed" | sed 's/^/  /'
  echo "=============================="
}

#------------------------------------------
# 執行單一 Agent
#------------------------------------------
cmd_run() {
  local agent="${1:-}"
  shift
  load_config "${CONFIG_FILE}"
  load_agents_from_config

  [[ -z "$agent" ]] && error "用法: $0 run <agent> [task]"

  local task="${*:-}"
  [[ -z "$task" ]] && task=$(get_agent_prompt "$agent" "$(jq_get "user_demand" "自訂任務")")

  local focus commit_msg
  focus=$(get_agent_focus "$agent" "")
  commit_msg=$(get_agent_commit "$agent")

  run_agent "$agent" "$task" "$focus" "$commit_msg"
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
  help|--help|-h) cat << 'EOF'
用法:
  ./runner.sh start  "需求描述" [config.yaml]  啟動完整工作流
  ./runner.sh resume [config.yaml]             從中斷點繼續
  ./runner.sh status [config.yaml]             查看狀態
  ./runner.sh run <agent> [task]              執行單一 Agent

範例:
  ./runner.sh start "新增會員點數功能"
  ./runner.sh start "新功能" config.myproject.yaml
  ./runner.sh status
  ./runner.sh resume
  ./runner.sh run backend-dev "優化資料庫查詢"

提示:
  - 複製 config.yaml 為自訂設定檔，客製化 Agent 流程
  - 或 export PROJECT_ROOT=/path/to/project 覆寫設定
EOF
      ;;
  *)      error "未知命令: $COMMAND，執行 '$0 help' 查看幫助" ;;
esac
