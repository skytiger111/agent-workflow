#!/usr/bin/env python3
"""Agent Workflow Web UI — Flask 後端"""
import os, sys, json, subprocess, threading
import yaml
from flask import Flask, render_template, jsonify, request, Response, stream_with_context

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = BASE_DIR
SHARED = os.path.join(BASE_DIR, "shared-context")
ARTIFACTS_DIR = os.path.join(SHARED, "artifacts")
HANDOFF = os.path.join(BASE_DIR, "handoff.json")
LOG_FILE = os.path.join(BASE_DIR, "log.md")
RUNNER = os.path.join(BASE_DIR, "runner.sh")

# 全域：目前執行中的 subprocess
_running_proc = None
_proc_lock = threading.Lock()


# ──────────────────────────────────────────────
# 工具
# ──────────────────────────────────────────────

def load_yaml(name: str) -> dict:
    path = os.path.join(CONFIG_DIR, name if name.endswith(".yaml") else f"config.{name}.yaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_yaml(name: str, data: dict) -> None:
    path = os.path.join(CONFIG_DIR, name if name.endswith(".yaml") else f"config.{name}.yaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def load_handoff() -> dict:
    if os.path.exists(HANDOFF):
        with open(HANDOFF, encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_log() -> str:
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, encoding="utf-8") as f:
            return f.read()
    return ""


def list_configs() -> list[dict]:
    """列出所有 config*.yaml，含 name / version"""
    import glob
    files = sorted(glob.glob(os.path.join(CONFIG_DIR, "config*.yaml")))
    result = []
    for f in files:
        name = os.path.basename(f)
        try:
            with open(f, encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh)
            result.append({
                "name": name,
                "label": cfg.get("name", name),
                "version": cfg.get("version", ""),
                "project_root": cfg.get("project_root", ""),
            })
        except Exception:
            result.append({"name": name, "label": name, "version": "", "project_root": ""})
    return result


def list_artifacts() -> list[dict]:
    """列出 artifacts 目錄下的檔案（不含子目錄內容）"""
    if not os.path.exists(ARTIFACTS_DIR):
        return []
    result = []
    for f in sorted(os.listdir(ARTIFACTS_DIR)):
        fp = os.path.join(ARTIFACTS_DIR, f)
        if os.path.isfile(fp):
            result.append({
                "name": f,
                "size": os.path.getsize(fp),
                "modified": os.path.getmtime(fp),
            })
    return result


def run_workflow_stream(cmd: list[str]):
    """同步執行 runner.sh，yield 每行輸出"""
    global _running_proc
    with _proc_lock:
        if _running_proc and _running_proc.poll() is None:
            yield f"data: [ERROR] 已有工作流正在執行\n\n"
            return
        _running_proc = subprocess.Popen(
            cmd,
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    proc = _running_proc
    try:
        for line in proc.stdout:
            yield f"data: {line}"
        proc.wait()
    finally:
        with _proc_lock:
            if _running_proc == proc:
                _running_proc = None


# ──────────────────────────────────────────────
# 路由
# ──────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("workflow_ui.html")


# ── Config ────────────────────────────────────

@app.route("/api/configs")
def api_configs():
    return jsonify(list_configs())


@app.route("/api/config/<name>")
def api_get_config(name):
    try:
        return jsonify(load_yaml(name))
    except FileNotFoundError:
        return jsonify({"error": "檔案不存在"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/config", methods=["POST"])
def api_save_config():
    data = request.json
    name = data.get("name", "config.yaml")
    save_yaml(name, data)
    return jsonify({"ok": True, "name": name})


# ── Status / Handoff ───────────────────────────

@app.route("/api/status")
def api_status():
    return jsonify(load_handoff())


# ── Artifacts ─────────────────────────────────

@app.route("/api/artifacts")
def api_artifacts():
    return jsonify(list_artifacts())


@app.route("/api/artifacts/<path:filename>")
def api_artifact(filename):
    path = os.path.join(ARTIFACTS_DIR, filename)
    if not os.path.isfile(path):
        return jsonify({"error": "檔案不存在"}), 404
    with open(path, encoding="utf-8") as f:
        content = f.read()
    return jsonify({"name": filename, "content": content})


# ── Log ───────────────────────────────────────

@app.route("/api/log")
def api_log():
    return jsonify({"content": load_log()})


# ── Workflow ──────────────────────────────────

@app.route("/api/workflow/poll")
def api_poll():
    with _proc_lock:
        running = _running_proc is not None and _running_proc.poll() is None
        pid = _running_proc.pid if _running_proc else None
    return jsonify({"running": running, "pid": pid})


@app.route("/api/workflow/start", methods=["POST"])
def api_start():
    body = request.json or {}
    demand = body.get("demand", "")
    config = body.get("config", "config.yaml")
    if not demand:
        return jsonify({"error": "請提供需求描述"}), 400
    cmd = [RUNNER, "start", demand, os.path.join(CONFIG_DIR, config)]
    # 非同步啟動，馬上回應
    thread = threading.Thread(target=lambda: list(run_workflow_stream(cmd)), daemon=True)
    thread.start()
    return jsonify({"ok": True, "started": demand})


@app.route("/api/workflow/resume", methods=["POST"])
def api_resume():
    body = request.json or {}
    config = body.get("config", "config.yaml")
    cmd = [RUNNER, "resume", os.path.join(CONFIG_DIR, config)]
    thread = threading.Thread(target=lambda: list(run_workflow_stream(cmd)), daemon=True)
    thread.start()
    return jsonify({"ok": True})


@app.route("/api/workflow/run", methods=["POST"])
def api_run_agent():
    body = request.json or {}
    agent = body.get("agent", "")
    task = body.get("task", "")
    config = body.get("config", "config.yaml")
    if not agent:
        return jsonify({"error": "請指定 agent"}), 400
    cmd = [RUNNER, "run", agent, task, os.path.join(CONFIG_DIR, config)]
    thread = threading.Thread(target=lambda: list(run_workflow_stream(cmd)), daemon=True)
    thread.start()
    return jsonify({"ok": True, "agent": agent})


@app.route("/api/workflow/stream")
def api_stream():
    """SSE 串流 runner.sh 輸出"""
    return Response(
        stream_with_context(run_workflow_stream([])),
        mimetype="text/event-stream",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5500, debug=True, threaded=True)
