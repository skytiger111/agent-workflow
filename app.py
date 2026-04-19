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
HANDOFF = os.path.join(BASE_DIR, "handoff.json")


def get_artifacts_dir() -> str:
    """從 handoff.json 讀取 per-project artifacts 目錄
    向後相容：若 handoff 無 artifacts 欄位，fallback 回 shared-context/artifacts/"""
    handoff = load_handoff()
    artifacts_cfg = handoff.get("artifacts", {})
    if artifacts_cfg and artifacts_cfg.get("spec"):
        return os.path.dirname(artifacts_cfg["spec"])
    # fallback：嘗試從 handoff.project_name 重建路徑
    project_name = handoff.get("project_name", "default")
    fallback = os.path.join(BASE_DIR, "projects", project_name, "artifacts")
    if os.path.exists(fallback):
        return fallback
    # 最終 fallback：舊的 shared-context/artifacts/（向後相容）
    return os.path.join(BASE_DIR, "shared-context", "artifacts")
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
                "label": cfg.get("name", name) if cfg else name,
                "version": cfg.get("version", "") if cfg else "",
                "project_root": cfg.get("project_root", "") if cfg else "",
            })
        except Exception:
            result.append({"name": name, "label": name, "version": "", "project_root": ""})
    return result


def list_artifacts() -> list[dict]:
    """列出 artifacts 目錄下的檔案（不含子目錄內容）"""
    artifacts_dir = get_artifacts_dir()
    if not os.path.exists(artifacts_dir):
        return []
    result = []
    for f in sorted(os.listdir(artifacts_dir)):
        fp = os.path.join(artifacts_dir, f)
        if os.path.isfile(fp):
            result.append({
                "name": f,
                "size": os.path.getsize(fp),
                "modified": os.path.getmtime(fp),
            })
    return result


def start_workflow(cmd: list[str]) -> None:
    """啟動 workflow subprocess（由執行緒呼叫，不讀 output）"""
    global _running_proc
    with _proc_lock:
        _running_proc = subprocess.Popen(
            cmd,
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    # 不等待完成！立即回傳 HTTP response，讓 SSE 有機會在 runner 執行期間連接
    # runner.sh 結束後由 watchdog thread 負責清理 _running_proc
    def cleanup():
        proc = _running_proc
        try:
            proc.wait()
        finally:
            with _proc_lock:
                if _running_proc == proc:
                    _running_proc = None
    threading.Thread(target=cleanup, daemon=True).start()


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
    path = os.path.join(get_artifacts_dir(), filename)
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
    thread = threading.Thread(target=start_workflow, args=(cmd,), daemon=True)
    thread.start()
    return jsonify({"ok": True, "started": demand})


@app.route("/api/workflow/resume", methods=["POST"])
def api_resume():
    body = request.json or {}
    config = body.get("config", "config.yaml")
    cmd = [RUNNER, "resume", os.path.join(CONFIG_DIR, config)]
    thread = threading.Thread(target=start_workflow, args=(cmd,), daemon=True)
    thread.start()
    return jsonify({"ok": True})


@app.route("/api/pipeline")
def api_pipeline():
    """合併 handoff + git log，給 Pipeline Tab 使用"""
    handoff = load_handoff()
    agents_cfg = handoff.get("agent_list", [])
    completed_list = handoff.get("completed_agent", [])
    if not isinstance(completed_list, list):
        completed_list = []
    current = handoff.get("current_agent", "")
    focus = handoff.get("focus_for_next", "")
    status = handoff.get("status", "unknown")

    agents = []
    for name in agents_cfg:
        if name == current and status == "in_progress":
            st = "running"
        elif name in completed_list:
            st = "done"
        else:
            st = "pending"
        agent = {"name": name, "status": st}
        if st == "running":
            agent["focus"] = focus
        agents.append(agent)

    # 讀取 git log（最多 10 筆）
    commits = []
    root = handoff.get("project_root", "")
    if root and os.path.exists(root):
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-10"],
                cwd=root, capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split(" ", 1)
                    commits.append({"hash": parts[0], "msg": parts[1] if len(parts) > 1 else ""})
        except Exception:
            pass

    return jsonify({
        "agents": agents,
        "commits": commits,
        "round": handoff.get("round", 0),
        "config_file": handoff.get("config_file", ""),
        "project_root": handoff.get("project_root", ""),
        "status": status,
        "focus": focus,
    })


@app.route("/api/workflow/run", methods=["POST"])
def api_run_agent():
    body = request.json or {}
    agent = body.get("agent", "")
    task = body.get("task", "")
    config = body.get("config", "config.yaml")
    if not agent:
        return jsonify({"error": "請指定 agent"}), 400
    cmd = [RUNNER, "run", agent, task, os.path.join(CONFIG_DIR, config)]
    thread = threading.Thread(target=start_workflow, args=(cmd,), daemon=True)
    thread.start()
    return jsonify({"ok": True, "agent": agent})


@app.route("/api/workflow/stream")
def api_stream():
    """SSE 串流 runner.sh 輸出（直接讀 _running_proc 的 stdout）"""
    def generate():
        import time
        # 等候最多 3 秒讓執行緒啟動並寫入 _running_proc
        for _ in range(30):
            with _proc_lock:
                proc = _running_proc
            if proc is not None:
                break
            yield f"data: [connecting]\n\n"
            time.sleep(0.1)

        while True:
            with _proc_lock:
                proc = _running_proc
            if proc is None or proc.poll() is not None:
                break
            try:
                line = proc.stdout.readline()
                if line:
                    yield f"data: {line}"
                else:
                    time.sleep(0.05)
            except Exception:
                break
        yield "data: [done]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5500, debug=True, threaded=True)
