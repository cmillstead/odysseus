from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

import routes.run_routes as run_routes
from core.database import Base, ScheduledTask, TaskRun
from services.runs.registry import RunRegistry


def _registry(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'runs.db'}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return RunRegistry(factory), factory


def test_run_registry_lifecycle_approvals_and_artifacts(tmp_path):
    registry, _ = _registry(tmp_path)

    run = registry.create_run(
        run_type="agent",
        title="Long agent task",
        owner="alice",
        status="running",
        objective="Do the long thing",
    )
    registry.append_event(run["id"], "progress", "Working", payload={"step": 1}, owner="alice")
    approval = registry.create_approval(run["id"], title="Delete file?", owner="alice")
    registry.add_artifact(run["id"], name="report.md", artifact_type="report", uri="/report.md", owner="alice")

    waiting = registry.get_run(run["id"], owner="alice")
    assert waiting["status"] == "waiting_for_approval"
    assert waiting["artifacts"][0]["name"] == "report.md"
    assert any(e["approval_status"] == "pending" for e in waiting["events"])

    registry.resolve_approval(run["id"], approval["approval_id"], owner="alice", approved=True)
    registry.update_run(run["id"], owner="alice", status="succeeded", summary="Done")

    done = registry.get_run(run["id"], owner="alice")
    assert done["status"] == "succeeded"
    assert done["summary"] == "Done"
    assert any(e["event_type"] == "approval_resolved" for e in done["events"])


def test_registry_adopts_task_runs_with_owner_scope(tmp_path):
    registry, factory = _registry(tmp_path)
    db = factory()
    try:
        db.add_all([
            ScheduledTask(id="task-a", owner="alice", name="Alice task", status="active"),
            ScheduledTask(id="task-b", owner="bob", name="Bob task", status="active"),
            TaskRun(id="run-a", task_id="task-a", status="success", result="ok"),
            TaskRun(id="run-b", task_id="task-b", status="error", error="nope"),
        ])
        db.commit()
    finally:
        db.close()

    rows = registry.sync_recent_task_runs(owner="alice")

    assert len(rows) == 1
    assert rows[0]["external_id"] == "run-a"
    assert rows[0]["status"] == "succeeded"
    assert registry.list_runs(owner="bob") == []


def test_run_routes_are_owner_scoped_and_resolve_approvals(monkeypatch, tmp_path):
    registry, _ = _registry(tmp_path)
    alice = registry.create_run(run_type="agent", title="Alice", owner="alice", status="running")
    bob = registry.create_run(run_type="agent", title="Bob", owner="bob", status="running")
    approval = registry.create_approval(alice["id"], title="Proceed?", owner="alice")

    monkeypatch.setattr(run_routes, "get_current_user", lambda request: "alice")
    app = FastAPI()
    app.include_router(run_routes.setup_run_routes(registry=registry))
    client = TestClient(app)

    listed = client.get("/api/runs").json()["runs"]
    assert [row["id"] for row in listed] == [alice["id"]]
    assert client.get(f"/api/runs/{bob['id']}").status_code == 404

    res = client.post(f"/api/runs/{alice['id']}/approvals/{approval['approval_id']}/approve")
    assert res.status_code == 200
    assert res.json()["run"]["status"] == "running"

    cancel = client.post(f"/api/runs/{alice['id']}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["run"]["status"] == "cancelled"
