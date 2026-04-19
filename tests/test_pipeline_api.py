# -*- coding: utf-8 -*-
"""test_pipeline_api.py — TDD for /api/pipeline endpoint"""
import os
import json
import pytest

# ---------------------------------------------------------------------------
# 測試資料 helper：建立 temp handoff.json
# ---------------------------------------------------------------------------
def make_handoff(tmp_dir, data):
    path = os.path.join(tmp_dir, "handoff.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


# ---------------------------------------------------------------------------
# 情境 A: 正常 workflow（completed + current agent）
# ---------------------------------------------------------------------------
def test_pipeline_normal(workflow_app, tmp_path):
    """有 completed_agent 和 current_agent 時，回傳正確的 agents 列表"""
    handoff_data = {
        "round": 3,
        "current_agent": "frontend-dev",
        "completed_agent": ["analyzer", "backend-dev"],
        "agent_list": ["analyzer", "backend-dev", "frontend-dev", "tester", "deployer"],
        "focus_for_next": "依據 API 合約實作前端 UI",
        "status": "in_progress",
    }
    hp = make_handoff(tmp_path, handoff_data)

    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "SPEC.md").write_text("# SPEC", encoding="utf-8")

    import app as _app
    orig_handoff = _app.HANDOFF
    orig_artifacts = _app.ARTIFACTS_DIR
    _app.HANDOFF = hp
    _app.ARTIFACTS_DIR = str(artifact_dir)

    try:
        client = workflow_app.test_client()
        rv = client.get("/api/pipeline")
        assert rv.status_code == 200
        data = rv.get_json()

        assert "agents" in data
        agents = data["agents"]
        assert len(agents) == 5

        assert agents[0]["name"] == "analyzer"
        assert agents[0]["status"] == "done"

        assert agents[1]["name"] == "backend-dev"
        assert agents[1]["status"] == "done"

        assert agents[2]["name"] == "frontend-dev"
        assert agents[2]["status"] == "running"
        assert agents[2]["focus"] == "依據 API 合約實作前端 UI"

        assert agents[3]["name"] == "tester"
        assert agents[3]["status"] == "pending"

        assert agents[4]["name"] == "deployer"
        assert agents[4]["status"] == "pending"
    finally:
        _app.HANDOFF = orig_handoff
        _app.ARTIFACTS_DIR = orig_artifacts


# ---------------------------------------------------------------------------
# 情境 B: workflow 未啟動（空 handoff）
# ---------------------------------------------------------------------------
def test_pipeline_empty(workflow_app, tmp_path):
    """handoff.json 為空或無 agent_list 時，回傳空 agents"""
    hp = make_handoff(tmp_path, {})

    import app as _app
    orig_handoff = _app.HANDOFF
    _app.HANDOFF = hp

    try:
        client = workflow_app.test_client()
        rv = client.get("/api/pipeline")
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["agents"] == []
    finally:
        _app.HANDOFF = orig_handoff


# ---------------------------------------------------------------------------
# 情境 C: workflow 已完成
# ---------------------------------------------------------------------------
def test_pipeline_completed(workflow_app, tmp_path):
    """status=completed 時，所有 agents 皆為 done"""
    handoff_data = {
        "round": 5,
        "current_agent": "",
        "completed_agent": ["analyzer", "backend-dev", "frontend-dev", "tester", "deployer"],
        "agent_list": ["analyzer", "backend-dev", "frontend-dev", "tester", "deployer"],
        "status": "completed",
    }
    hp = make_handoff(tmp_path, handoff_data)

    import app as _app
    orig_handoff = _app.HANDOFF
    _app.HANDOFF = hp

    try:
        client = workflow_app.test_client()
        rv = client.get("/api/pipeline")
        assert rv.status_code == 200
        data = rv.get_json()
        for a in data["agents"]:
            assert a["status"] == "done", f"{a['name']} 應為 done，實際為 {a['status']}"
    finally:
        _app.HANDOFF = orig_handoff


# ---------------------------------------------------------------------------
# 情境 D: 自訂 agent 數量（不同 pipeline 設定）
# ---------------------------------------------------------------------------
def test_pipeline_custom_agents(workflow_app, tmp_path):
    """pipeline 只有 3 個 agent 時，正確呈現"""
    handoff_data = {
        "round": 1,
        "current_agent": "backend-dev",
        "completed_agent": ["planner"],
        "agent_list": ["planner", "backend-dev", "deployer"],
        "status": "in_progress",
    }
    hp = make_handoff(tmp_path, handoff_data)

    import app as _app
    orig_handoff = _app.HANDOFF
    _app.HANDOFF = hp

    try:
        client = workflow_app.test_client()
        rv = client.get("/api/pipeline")
        assert rv.status_code == 200
        data = rv.get_json()
        assert len(data["agents"]) == 3
        assert [a["name"] for a in data["agents"]] == ["planner", "backend-dev", "deployer"]
    finally:
        _app.HANDOFF = orig_handoff


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def workflow_app():
    """建立乾淨的 Flask app（不啟動 server）"""
    import app as _app
    _app.app.config["TESTING"] = True
    return _app.app
