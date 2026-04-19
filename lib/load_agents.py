#!/usr/bin/env python3
"""讀取 config.yaml 的 agents 列表 — 供 runner.sh 呼叫"""
import yaml, sys

cfg_path = sys.argv[1] if len(sys.argv) > 1 else ""
if not cfg_path:
    print("ERROR: no config path", file=sys.stderr)
    sys.exit(1)

try:
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
    for agent in cfg.get("agents", []):
        name = agent.get("name", "")
        if name:
            print(name)
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
