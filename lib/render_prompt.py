#!/usr/bin/env python3
"""render_prompt.py — 替換 prompt 模板中的變數（支援多行內容）"""
import sys
import subprocess
import os

TEMPLATE = sys.argv[1] if len(sys.argv) > 1 else ""
USER_DEMAND = os.environ.get("USER_DEMAND", "")
PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "")
ARTIFACTS_DIR = os.environ.get("ARTIFACTS_DIR", "")
HANDOFF = os.environ.get("HANDOFF", "")
GIT_REMOTE = os.environ.get("GIT_REMOTE", "")
GIT_BRANCH = os.environ.get("GIT_BRANCH", "")

# 取得 project_files（list_project_files 邏輯）
project_root = PROJECT_ROOT or "."
try:
    result = subprocess.run(
        ["find", ".", "-maxdepth", "3", "-type", "f",
         "(", "-name", "*.py", "-o", "-name", "*.js", "-o", "-name", "*.html",
         "-o", "-name", "*.css", "-o", "-name", "*.yaml", "-o", "-name", "*.json", ")",
         "-not", "-path", "./node_modules/*", "-not", "-path", "./.git/*"],
        cwd=project_root,
        capture_output=True, text=True, timeout=5
    )
    project_files = result.stdout.strip()[:2000]  # 限制長度
except Exception:
    project_files = "(無法取得)"

output = TEMPLATE
output = output.replace("{user_demand}", USER_DEMAND)
output = output.replace("{project_root}", PROJECT_ROOT)
output = output.replace("{artifacts_dir}", ARTIFACTS_DIR)
output = output.replace("{handoff_file}", HANDOFF)
output = output.replace("{git_remote}", GIT_REMOTE)
output = output.replace("{git_branch}", GIT_BRANCH)
output = output.replace("{project_files}", project_files)

print(output, end="")
