import json, sys, os
from datetime import datetime, timezone

def write_handoff(handoff_path, artifacts_dir, round_n, agent, next_agent, outputs, focus):
    with open(handoff_path) as f:
        data = json.load(f)

    completed = data.get("completed_agent") or []

    # 加入當前 agent（防重複）
    if agent not in completed:
        completed.append(agent)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    data.update({
        "round": round_n,
        "current_agent": agent,
        "next_agent": next_agent,
        "completed_agent": completed,
        "last_outputs": [outputs],
        "focus_for_next": focus,
        "timestamp": ts,
        "status": "in_progress",
        "artifacts": {
            "spec": f"{artifacts_dir}/SPEC.md",
            "api_contract": f"{artifacts_dir}/api-contract.md",
            "frontend_spec": f"{artifacts_dir}/component-spec.md",
            "test_report": f"{artifacts_dir}/test-report.md",
            "deploy_status": f"{artifacts_dir}/deploy-status.md",
        }
    })

    with open(handoff_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    write_handoff(
        sys.argv[1],  # handoff_path
        sys.argv[2],  # artifacts_dir
        int(sys.argv[3]),  # round
        sys.argv[4],  # agent
        sys.argv[5],  # next_agent
        sys.argv[6],  # outputs
        sys.argv[7]   # focus
    )
    print(f"handoff.json updated: round={sys.argv[3]}, agent={sys.argv[4]}, next={sys.argv[5]}")
