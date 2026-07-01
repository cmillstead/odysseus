from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

import routes.run_routes as run_routes
import services.runs.executors as run_executors
from core.database import Base
from services.runs.executors import RunExecutorManager
from services.runs.registry import RunRegistry


def _registry(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'runs-v2.db'}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return RunRegistry(factory), factory


def test_local_agent_reconcile_marks_missing_stream_blocked(tmp_path):
    registry, _ = _registry(tmp_path)
    run = registry.create_run(
        run_type="agent",
        title="Detached stream",
        owner="alice",
        executor="local_agent",
        external_type="agent_stream",
        external_id="session-a:dead",
        session_id=None,
        status="running",
    )
    manager = RunExecutorManager(registry)

    changed = manager.reconcile_active_agent_runs(owner="alice")

    assert changed
    blocked = registry.get_run(run["id"], owner="alice")
    assert blocked["status"] == "blocked"
    assert blocked["metadata"]["restart_recovery_state"] == "worker_missing"
    assert any(e["event_type"] == "restart_recovery" for e in blocked["events"])


def test_sandbox_executor_creates_workspace_artifact_and_subrun(tmp_path, monkeypatch):
    monkeypatch.setattr(run_executors, "DATA_DIR", str(tmp_path))
    registry, _ = _registry(tmp_path)
    manager = RunExecutorManager(registry)

    parent = manager.launch(
        executor="sandbox_agent",
        title="Hermes sandbox",
        objective="Investigate",
        owner="alice",
        autonomy="trusted_local",
    )
    child = manager.create_subrun(
        parent,
        executor="sandbox_agent",
        title="Parallel test",
        objective="Run tests",
    )

    full = registry.get_run(parent["id"], owner="alice")
    assert full["metadata"]["sandbox_provider"] == "local"
    assert full["metadata"]["autonomy"] == "trusted_local"
    assert full["artifacts"][0]["artifact_type"] == "sandbox_manifest"
    assert full["children"][0]["id"] == child["id"]


def test_run_v2_api_inputs_pause_subrun_stream_and_owner_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(run_executors, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(run_routes, "get_current_user", lambda request: "alice")
    registry, _ = _registry(tmp_path)
    app = FastAPI()
    app.include_router(run_routes.setup_run_routes(registry=registry))
    client = TestClient(app)

    executors = client.get("/api/run-executors")
    assert executors.status_code == 200
    assert {row["name"] for row in executors.json()["executors"]} >= {"local_agent", "sandbox_agent"}

    created = client.post(
        "/api/runs",
        json={
            "executor": "sandbox_agent",
            "title": "API sandbox",
            "objective": "Do it",
            "autonomy": "manual",
        },
    )
    assert created.status_code == 200
    run = created.json()["run"]
    assert run["executor"] == "sandbox_agent"

    queued = client.post(f"/api/runs/{run['id']}/inputs", json={"content": "Follow up"})
    assert queued.status_code == 200
    assert queued.json()["run"]["current_step"] == "Follow-up queued"

    paused = client.post(f"/api/runs/{run['id']}/pause")
    assert paused.status_code == 200
    assert paused.json()["run"]["status"] == "paused"

    resumed = client.post(f"/api/runs/{run['id']}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["run"]["status"] == "running"

    subrun = client.post(
        f"/api/runs/{run['id']}/subruns",
        json={"title": "Child run", "objective": "Parallel work", "executor": "sandbox_agent"},
    )
    assert subrun.status_code == 200
    assert subrun.json()["run"]["parent_run_id"] == run["id"]

    cancelled = client.post(f"/api/runs/{run['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["run"]["status"] == "cancelled"

    stream = client.get(f"/api/runs/{run['id']}/stream")
    assert stream.status_code == 200
    assert "event: run_event" in stream.text
    assert "event: run_snapshot" in stream.text

    monkeypatch.setattr(run_routes, "get_current_user", lambda request: "bob")
    assert client.get(f"/api/runs/{run['id']}").status_code == 404
