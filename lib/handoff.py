#!/usr/bin/env python3
"""handoff.json 操作工具 — 供 runner.sh 呼叫"""
import json, sys, os
from datetime import datetime, timezone

# 解析引數：artifacts_dir handoff_path command [args...]
_artifacts = sys.argv[1] if len(sys.argv) > 1 else ""
_handoff_path = sys.argv[2] if len(sys.argv) > 2 else "handoff.json"
COMMAND = sys.argv[3] if len(sys.argv) > 3 else ""

TS = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def load():
    if os.path.exists(_handoff_path):
        with open(_handoff_path) as f:
            return json.load(f)
    return {}

def save(data):
    with open(_handoff_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def cmd_init():
    """初始化一個新的 handoff.json"""
    user_demand = sys.argv[4] if len(sys.argv) > 4 else ""
    agents_raw = sys.argv[5] if len(sys.argv) > 5 else "[]"
    config_file = sys.argv[6] if len(sys.argv) > 6 else ""
    project_name = sys.argv[7] if len(sys.argv) > 7 else "default"
    project_root = sys.argv[8] if len(sys.argv) > 8 else ""
    git_remote = sys.argv[9] if len(sys.argv) > 9 else ""
    try:
        agents = json.loads(agents_raw)
    except:
        agents = []

    next_agent = agents[0] if agents else "analyzer"

    # 動態計算 artifacts 路徑（與 runner.sh 保持一致）
    workflow_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    artifacts_base = os.path.join(workflow_dir, "projects", project_name, "artifacts")
    art_paths = {
        "spec": f"{artifacts_base}/SPEC.md",
        "api_contract": f"{artifacts_base}/api-contract.md",
        "frontend_spec": f"{artifacts_base}/component-spec.md",
        "test_report": f"{artifacts_base}/test-report.md",
        "deploy_status": f"{artifacts_base}/deploy-status.md",
    }

    save({
        "round": 0,
        "current_agent": None,
        "next_agent": next_agent,
        "completed_agent": [],
        "user_demand": user_demand,
        "last_outputs": [],
        "focus_for_next": "",
        "timestamp": TS,
        "status": "in_progress",
        "agent_list": agents,
        "artifacts": art_paths,
        "project_name": project_name,
        "project_root": project_root,
        "git_remote": git_remote,
        "config_file": config_file,
    })
    print(f"[OK] handoff.json initialized (next: {next_agent}, config: {config_file}, project: {project_name})")

def cmd_update():
    """更新 handoff：設定當前/下一個 agent"""
    round_n = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    agent = sys.argv[5] if len(sys.argv) > 5 else ""
    next_agent = sys.argv[6] if len(sys.argv) > 6 else ""
    outputs = sys.argv[7] if len(sys.argv) > 7 else ""
    focus = sys.argv[8] if len(sys.argv) > 8 else ""
    mark_done = (sys.argv[9] if len(sys.argv) > 9 else "true").lower() == "true"

    data = load()
    completed = data.get("completed_agent") or []
    if mark_done and agent not in completed:
        completed.append(agent)

    # 不覆蓋 status：若已達 completed，維持 completed
    if data.get("status") != "completed":
        data["status"] = "in_progress"
    data.update({
        "round": round_n,
        "current_agent": agent,
        "next_agent": next_agent,
        "completed_agent": completed,
        "last_outputs": [outputs],
        "focus_for_next": focus,
        "timestamp": TS,
        # 保留 init 時寫入的專案資訊
        "project_name": data.get("project_name", ""),
        "project_root": data.get("project_root", ""),
        "git_remote": data.get("git_remote", ""),
        "config_file": data.get("config_file", ""),
    })
    save(data)
    print(f"[OK] handoff updated: round={round_n}, agent={agent}, next={next_agent}")

def cmd_complete():
    """標記工作流完成"""
    data = load()
    data["status"] = "completed"
    data["completed_at"] = TS
    save(data)
    print("[OK] workflow completed")

def cmd_get():
    """讀取指定欄位"""
    key = sys.argv[4] if len(sys.argv) > 4 else ""
    data = load()
    val = data.get(key, "")
    if isinstance(val, (list, dict)):
        print(json.dumps(val, ensure_ascii=False))
    else:
        print(val)

if __name__ == "__main__":
    if COMMAND == "init":
        cmd_init()
    elif COMMAND == "update":
        cmd_update()
    elif COMMAND == "complete":
        cmd_complete()
    elif COMMAND == "get":
        cmd_get()
    else:
        print(f"Unknown command: {COMMAND}", file=sys.stderr)
        sys.exit(1)
