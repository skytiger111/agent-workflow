#!/usr/bin/env python3
"""即時串流 Agent 輸出：邊 tail 檔案邊寫入固定路徑，供 Flask SSE 直接讀取。"""
import sys, os, time

OUTPUT_FIXED = os.path.join(os.path.dirname(__file__), "..", "shared-context", ".agent_output")

if len(sys.argv) < 2:
    output_file = OUTPUT_FIXED
else:
    output_file = sys.argv[1]

MAX_LINES = 500
count = 0

# 等 agent 開始寫入（最多 3 秒）
for _ in range(60):
    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
        break
    time.sleep(0.05)

last_pos = 0

while True:
    if not os.path.exists(output_file):
        break
    try:
        size = os.path.getsize(output_file)
        if size > last_pos:
            with open(output_file, "r", encoding="utf-8", errors="replace") as f:
                f.seek(last_pos)
                for line in f:
                    if count >= MAX_LINES:
                        break
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    count += 1
            last_pos = size
    except Exception:
        pass

    # 檔案大小不再變 → agent 可能結束
    time.sleep(0.3)
    if os.path.exists(output_file) and os.path.getsize(output_file) == last_pos:
        # 再等一次確認不是还在写
        time.sleep(1.0)
        if os.path.exists(output_file) and os.path.getsize(output_file) == last_pos:
            break

    if count >= MAX_LINES:
        sys.stdout.write(f"\n...（已截斷顯示，共 {MAX_LINES} 行）\n")
        break

sys.exit(0)
