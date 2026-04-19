#!/usr/bin/env python3
"""查詢 config.yaml — 供 runner.sh 呼叫"""
import yaml, sys

cfg_path = sys.argv[1] if len(sys.argv) > 1 else ""
mode = sys.argv[2] if len(sys.argv) > 2 else ""
agent = sys.argv[3] if len(sys.argv) > 3 else ""

if not cfg_path:
    print("ERROR: no config path", file=sys.stderr)
    sys.exit(1)

try:
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)

if mode == "agents":
    for a in cfg.get("agents", []):
        name = a.get("name", "")
        if name:
            print(name)

elif mode == "project_root":
    print(cfg.get("project_root", ""))

elif mode == "git_remote":
    print(cfg.get("git_remote", ""))

elif mode == "git_branch":
    print(cfg.get("git_branch", "main"))

elif mode == "handoff_footer":
    footer = cfg.get("handoff_footer", "")
    print(footer)

elif mode == "agent_prompt":
    for a in cfg.get("agents", []):
        if a.get("name") == agent:
            print(a.get("prompt_template", ""))
            break

elif mode == "agent_focus":
    for a in cfg.get("agents", []):
        if a.get("name") == agent:
            print(a.get("description", ""))
            break

elif mode == "agent_commit":
    for a in cfg.get("agents", []):
        if a.get("name") == agent:
            print(a.get("commit_message", ""))
            break

elif mode == "name":
    print(cfg.get("name", ""))

else:
    print(f"ERROR: unknown mode: {mode}", file=sys.stderr)
    sys.exit(1)
