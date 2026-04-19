#!/usr/bin/env python3
"""即時串流 Agent 輸出到 stdout（送 Flask SSE pipe），同時寫入檔案。"""
import sys, os, time, threading

if len(sys.argv) < 2:
    print("Usage: stream_output.py <output_file> [pid_to_watch]", file=sys.stderr)
    sys.exit(1)

output_file = sys.argv[1]
watch_pid = int(sys.argv[2]) if len(sys.argv) > 2 else None
MAX_LINES = 200

# 等檔案出現
for _ in range(20):
    if os.path.exists(output_file):
        break
    time.sleep(0.1)

last_pos = 0
count = 0

def is_process_running(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

while True:
    if os.path.exists(output_file):
        try:
            size = os.path.getsize(output_file)
            if size > last_pos:
                with open(output_file, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(last_pos)
                    for line in f:
                        if count >= MAX_LINES:
                            break
                        # flush=True 確保送到 Flask SSE pipe
                        print(line, end="", flush=True)
                        count += 1
                last_pos = size
        except Exception:
            pass

    # 檢查 agent 行程是否已結束
    done = (watch_pid is not None and not is_process_running(watch_pid)) or (watch_pid is None and last_pos == 0)

    if done:
        time.sleep(0.3)
        if os.path.exists(output_file):
            try:
                size = os.path.getsize(output_file)
                if size > last_pos:
                    with open(output_file, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(last_pos)
                        for line in f:
                            if count >= MAX_LINES:
                                break
                            print(line, end="", flush=True)
                            count += 1
            except Exception:
                pass
        break

    if count >= MAX_LINES:
        print(f"\n...（已截斷顯示，共 {MAX_LINES} 行）", flush=True)
        break

    time.sleep(0.05)
