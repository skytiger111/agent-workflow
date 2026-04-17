#!/bin/bash
#===============================================
# Context Compactor — 每 5 輪執行一次
# 壓縮 log.md 中的歷史，產生 log-summary.md
#===============================================

WORKFLOW_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$WORKFLOW_DIR/log.md"
SUMMARY="$WORKFLOW_DIR/log-summary.md"

[[ ! -f "$LOG_FILE" ]] && echo "無 log.md，略過compact" && exit 0

# 讀取 handoff 的 round
ROUND=$(jq -r '.round' "$WORKFLOW_DIR/shared-context/handoff.json" 2>/dev/null || echo "0")

echo "Compactor 執行：round $ROUND"

# 擷取每輪摘要
summaries=$(grep -E "^## " "$LOG_FILE" | tail -10)

cat > "$SUMMARY" << EOF
# Log Summary（自動產生）

## 最新狀態

**Round:** $ROUND
**Generated:** $(date -u +%Y-%m-%dT%H:%M:%SZ)

## 近 10 輪摘要

$summaries

---
完整記錄：log.md
EOF

echo "log-summary.md 已更新"
