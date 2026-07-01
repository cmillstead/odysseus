"""Execution adapters for Unified Runs.

The registry owns durable visibility. Executors own best-effort control of the
underlying work and report their capability surface so the API/UI can stay
truthful about what a run can do.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from core.constants import DATA_DIR

from .registry import ACTIVE_STATUSES, RunRegistry, get_run_registry


AUTONOMY_MODES = {"manual", "review_gated", "trusted_local"}


def _now_unix() -> float:
    return time.time()


def _autonomy(value: Optional[str]) -> str:
    text = str(value or "review_gated").strip().lower()
    return text if text in AUTONOMY_MODES else "review_gated"


def _executor_from_run(run: dict[str, Any]) -> str:
    meta = run.get("metadata") or {}
    return str(run.get("executor") or meta.get("executor") or "local_agent")


@dataclass(frozen=True)
class ExecutorResult:
    ok: bool
    run: Optional[dict[str, Any]] = None
    message: str = ""
    adapter_cancelled: bool = False
    supported: bool = True

    def to_response(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "supported": self.supported,
            "adapter_cancelled": self.adapter_cancelled,
            "message": self.message,
            "run": self.run,
        }


class RunExecutor:
    """Synchronous control contract used by FastAPI routes."""

    name = "executor"
    label = "Executor"
    capabilities: dict[str, Any] = {}

    def __init__(self, registry: RunRegistry):
        self.registry = registry

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "capabilities": dict(self.capabilities),
        }

    def launch(
        self,
        *,
        title: str,
        objective: Optional[str],
        owner: Optional[str],
        session_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        model: Optional[str] = None,
        autonomy: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def cancel(self, run: dict[str, Any], *, owner: Optional[str] = None) -> ExecutorResult:
        updated = self.registry.update_run(
            run["id"],
            owner=owner,
            status="cancelled",
            current_step="Cancellation requested",
            event_type="cancel",
            event_message="Run cancellation requested",
        )
        return ExecutorResult(ok=True, run=updated, message="Cancellation requested")

    def pause(self, run: dict[str, Any], *, owner: Optional[str] = None) -> ExecutorResult:
        if not self.capabilities.get("pause"):
            return ExecutorResult(ok=False, run=run, message="Pause is not supported by this executor", supported=False)
        updated = self.registry.update_run(
            run["id"],
            owner=owner,
            status="paused",
            current_step="Paused",
            metadata={"paused_at": _now_unix()},
            event_type="pause",
            event_message="Run paused",
        )
        return ExecutorResult(ok=True, run=updated, message="Run paused")

    def resume(self, run: dict[str, Any], *, owner: Optional[str] = None) -> ExecutorResult:
        updated = self.registry.update_run(
            run["id"],
            owner=owner,
            status="running",
            current_step="Resumed",
            metadata={"resumed_at": _now_unix()},
            event_type="resume",
            event_message="Run resumed",
        )
        return ExecutorResult(ok=True, run=updated, message="Run resumed")

    def append_input(
        self,
        run: dict[str, Any],
        *,
        content: str,
        owner: Optional[str] = None,
        input_type: str = "user",
    ) -> ExecutorResult:
        payload = {
            "input_id": uuid.uuid4().hex,
            "input_type": input_type or "user",
            "content": content,
            "queued_at": _now_unix(),
        }
        self.registry.append_event(
            run["id"],
            "input_queued",
            "Follow-up input queued",
            payload=payload,
            owner=owner,
        )
        updated = self.registry.update_run(
            run["id"],
            owner=owner,
            current_step="Follow-up queued",
            metadata={"last_input_id": payload["input_id"], "last_input_at": payload["queued_at"]},
        )
        return ExecutorResult(ok=True, run=updated, message="Input queued")

    def resolve_approval(
        self,
        run: dict[str, Any],
        approval_id: str,
        *,
        owner: Optional[str] = None,
        approved: bool,
    ) -> ExecutorResult:
        event = self.registry.resolve_approval(run["id"], approval_id, owner=owner, approved=approved)
        updated = self.registry.get_run(run["id"], owner=owner)
        return ExecutorResult(ok=bool(event), run=updated, message="Approval resolved" if event else "Approval not found")

    def status(self, run: dict[str, Any], *, owner: Optional[str] = None) -> dict[str, Any]:
        return {
            "executor": self.name,
            "status": run.get("status"),
            "capabilities": dict(self.capabilities),
        }

    def collect_artifacts(self, run: dict[str, Any], *, owner: Optional[str] = None) -> list[dict[str, Any]]:
        return list(run.get("artifacts") or [])

    def reconcile(self, run: dict[str, Any], *, owner: Optional[str] = None) -> Optional[dict[str, Any]]:
        return None


class LocalAgentExecutor(RunExecutor):
    name = "local_agent"
    label = "Local Agent"
    capabilities = {
        "cancel": True,
        "pause": True,
        "resume": True,
        "inputs": True,
        "approvals": True,
        "artifacts": True,
        "subruns": True,
        "restart_recovery": "truthful_blocked",
        "durability": "registry_events",
    }

    def launch(
        self,
        *,
        title: str,
        objective: Optional[str],
        owner: Optional[str],
        session_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        model: Optional[str] = None,
        autonomy: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        meta = {
            "executor": self.name,
            "capabilities": self.capabilities,
            "autonomy": _autonomy(autonomy),
            "last_heartbeat_at": _now_unix(),
            "durability_scope": "local_process_with_registry_recovery",
            "restart_recovery": "block_if_worker_missing",
        }
        meta.update(metadata or {})
        run = self.registry.create_run(
            run_type="agent",
            title=title or "Local agent run",
            owner=owner,
            objective=objective,
            origin="runs",
            executor=self.name,
            backend="local",
            model=model,
            session_id=session_id,
            parent_run_id=parent_run_id,
            external_type="local_agent_run",
            external_id=uuid.uuid4().hex,
            status="running",
            current_step="Local agent run registered",
            metadata=meta,
        )
        if objective:
            self.append_input(run, content=objective, owner=owner, input_type="initial_objective")
        self.registry.append_event(
            run["id"],
            "checkpoint",
            "Durable run checkpoint created",
            payload={"checkpoint": "launch", "executor": self.name},
            owner=owner,
        )
        return self.registry.get_run(run["id"], owner=owner) or run

    def cancel(self, run: dict[str, Any], *, owner: Optional[str] = None) -> ExecutorResult:
        stopped = False
        if run.get("external_type") == "agent_stream" and run.get("session_id"):
            try:
                from src import agent_runs

                stopped = bool(agent_runs.stop(run["session_id"]))
            except Exception:
                stopped = False
        updated = self.registry.update_run(
            run["id"],
            owner=owner,
            status="cancelled",
            current_step="Cancelled" if stopped else "Cancellation requested",
            metadata={"cancel_requested_at": _now_unix(), "adapter_cancelled": stopped},
            event_type="cancel",
            event_message="Run cancelled" if stopped else "Cancellation requested",
        )
        return ExecutorResult(ok=True, run=updated, message="Run cancelled" if stopped else "Cancellation requested", adapter_cancelled=stopped)

    def pause(self, run: dict[str, Any], *, owner: Optional[str] = None) -> ExecutorResult:
        updated = self.registry.update_run(
            run["id"],
            owner=owner,
            status="paused",
            current_step="Paused; follow-ups will remain queued",
            metadata={"paused_at": _now_unix()},
            event_type="pause",
            event_message="Local agent pause requested",
        )
        return ExecutorResult(ok=True, run=updated, message="Run paused")

    def resume(self, run: dict[str, Any], *, owner: Optional[str] = None) -> ExecutorResult:
        meta = run.get("metadata") or {}
        blocked_reason = meta.get("restart_recovery_state")
        if blocked_reason == "worker_missing" and run.get("external_type") == "agent_stream":
            updated = self.registry.update_run(
                run["id"],
                owner=owner,
                status="blocked",
                current_step="Cannot resume this in-process stream after restart",
                error="The local chat stream worker is gone. Queue a follow-up or start a new background run.",
                event_type="resume_failed",
                event_message="Local stream cannot be resumed after process restart",
            )
            return ExecutorResult(ok=False, run=updated, message="Worker missing after restart")
        updated = self.registry.update_run(
            run["id"],
            owner=owner,
            status="running",
            current_step="Resumed",
            metadata={"resumed_at": _now_unix()},
            event_type="resume",
            event_message="Local agent resumed",
        )
        return ExecutorResult(ok=True, run=updated, message="Run resumed")

    def append_input(
        self,
        run: dict[str, Any],
        *,
        content: str,
        owner: Optional[str] = None,
        input_type: str = "user",
    ) -> ExecutorResult:
        result = super().append_input(run, content=content, owner=owner, input_type=input_type)
        self.registry.append_event(
            run["id"],
            "checkpoint",
            "Input checkpoint saved",
            payload={"kind": "queued_input"},
            owner=owner,
        )
        return result

    def reconcile(self, run: dict[str, Any], *, owner: Optional[str] = None) -> Optional[dict[str, Any]]:
        if run.get("status") not in {"queued", "running", "paused"}:
            return None
        if run.get("external_type") != "agent_stream":
            return None
        session_id = run.get("session_id")
        active = False
        if session_id:
            try:
                from src import agent_runs

                active = bool(agent_runs.is_active(session_id))
            except Exception:
                active = False
        if active:
            return self.registry.update_run(
                run["id"],
                owner=owner,
                metadata={"last_heartbeat_at": _now_unix(), "restart_recovery_state": "attached"},
            )
        return self.registry.update_run(
            run["id"],
            owner=owner,
            status="blocked",
            current_step="Local agent worker is no longer attached",
            error="The local in-process chat stream is no longer running. This usually means the app restarted or the worker exited before reporting a final state.",
            metadata={"restart_recovery_state": "worker_missing", "checked_at": _now_unix()},
            event_type="restart_recovery",
            event_message="Run marked blocked because the local worker is missing",
        )


class SandboxAgentExecutor(RunExecutor):
    name = "sandbox_agent"
    label = "Hermes Sandbox"
    capabilities = {
        "cancel": True,
        "pause": True,
        "resume": True,
        "inputs": True,
        "approvals": True,
        "artifacts": True,
        "subruns": True,
        "restart_recovery": "snapshot_metadata",
        "durability": "sandbox_workspace",
    }

    def _workspace_root(self) -> Path:
        root = Path(DATA_DIR) / "runs" / "sandboxes"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def launch(
        self,
        *,
        title: str,
        objective: Optional[str],
        owner: Optional[str],
        session_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        model: Optional[str] = None,
        autonomy: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        external_id = uuid.uuid4().hex
        workspace = self._workspace_root() / external_id
        artifacts_dir = workspace / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = workspace / "manifest.json"
        manifest = {
            "sandbox_id": external_id,
            "title": title or "Hermes sandbox run",
            "objective": objective or "",
            "created_at": _now_unix(),
            "provider": "local",
            "workspace": str(workspace),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        meta = {
            "executor": self.name,
            "capabilities": self.capabilities,
            "autonomy": _autonomy(autonomy),
            "sandbox_provider": "local",
            "sandbox_id": external_id,
            "workspace_path": str(workspace),
            "artifact_dir": str(artifacts_dir),
            "last_heartbeat_at": _now_unix(),
            "snapshot": {"manifest": str(manifest_path), "created_at": manifest["created_at"]},
        }
        meta.update(metadata or {})
        run = self.registry.create_run(
            run_type="agent",
            title=title or "Hermes sandbox run",
            owner=owner,
            objective=objective,
            origin="runs",
            executor=self.name,
            backend="local_sandbox",
            model=model,
            session_id=session_id,
            parent_run_id=parent_run_id,
            external_type="sandbox",
            external_id=external_id,
            status="running",
            current_step="Local sandbox workspace ready",
            metadata=meta,
        )
        self.registry.add_artifact(
            run["id"],
            name="manifest.json",
            artifact_type="sandbox_manifest",
            path=str(manifest_path),
            mime_type="application/json",
            owner=owner,
            metadata={"sandbox_id": external_id},
        )
        if objective:
            self.append_input(run, content=objective, owner=owner, input_type="initial_objective")
        self.registry.append_event(
            run["id"],
            "checkpoint",
            "Sandbox snapshot created",
            payload={"workspace": str(workspace), "manifest": str(manifest_path)},
            owner=owner,
        )
        return self.registry.get_run(run["id"], owner=owner) or run

    def cancel(self, run: dict[str, Any], *, owner: Optional[str] = None) -> ExecutorResult:
        updated = self.registry.update_run(
            run["id"],
            owner=owner,
            status="cancelled",
            current_step="Sandbox run cancelled",
            metadata={"cancel_requested_at": _now_unix()},
            event_type="cancel",
            event_message="Sandbox run cancelled",
        )
        return ExecutorResult(ok=True, run=updated, message="Sandbox run cancelled", adapter_cancelled=True)

    def collect_artifacts(self, run: dict[str, Any], *, owner: Optional[str] = None) -> list[dict[str, Any]]:
        meta = run.get("metadata") or {}
        artifact_dir = meta.get("artifact_dir")
        if artifact_dir and os.path.isdir(artifact_dir):
            for path in Path(artifact_dir).iterdir():
                if path.is_file():
                    self.registry.add_artifact(
                        run["id"],
                        name=path.name,
                        artifact_type="file",
                        path=str(path),
                        owner=owner,
                    )
        refreshed = self.registry.get_run(run["id"], owner=owner) or run
        return list(refreshed.get("artifacts") or [])

    def reconcile(self, run: dict[str, Any], *, owner: Optional[str] = None) -> Optional[dict[str, Any]]:
        if run.get("status") not in ACTIVE_STATUSES:
            return None
        meta = run.get("metadata") or {}
        workspace = meta.get("workspace_path")
        if workspace and os.path.isdir(workspace):
            return self.registry.update_run(
                run["id"],
                owner=owner,
                metadata={"last_heartbeat_at": _now_unix(), "restart_recovery_state": "workspace_present"},
            )
        return self.registry.update_run(
            run["id"],
            owner=owner,
            status="blocked",
            current_step="Sandbox workspace is missing",
            error="The local sandbox workspace could not be found during restart reconciliation.",
            metadata={"restart_recovery_state": "workspace_missing", "checked_at": _now_unix()},
            event_type="restart_recovery",
            event_message="Run marked blocked because the sandbox workspace is missing",
        )


class RunExecutorManager:
    def __init__(self, registry: Optional[RunRegistry] = None):
        self.registry = registry or get_run_registry()
        self.executors: dict[str, RunExecutor] = {
            LocalAgentExecutor.name: LocalAgentExecutor(self.registry),
            SandboxAgentExecutor.name: SandboxAgentExecutor(self.registry),
        }

    def get(self, name: Optional[str]) -> RunExecutor:
        return self.executors.get(name or "", self.executors[LocalAgentExecutor.name])

    def get_for_run(self, run: dict[str, Any]) -> RunExecutor:
        return self.get(_executor_from_run(run))

    def describe(self) -> list[dict[str, Any]]:
        return [executor.describe() for executor in self.executors.values()]

    def launch(self, *, executor: str = "local_agent", **kwargs: Any) -> dict[str, Any]:
        return self.get(executor).launch(**kwargs)

    def create_subrun(self, parent: dict[str, Any], *, executor: Optional[str] = None, **kwargs: Any) -> dict[str, Any]:
        selected = executor or _executor_from_run(parent)
        metadata = dict(kwargs.pop("metadata", {}) or {})
        metadata["parent_run_id"] = parent.get("id")
        metadata["parent_executor"] = _executor_from_run(parent)
        return self.launch(
            executor=selected,
            parent_run_id=parent.get("id"),
            owner=parent.get("owner"),
            metadata=metadata,
            **kwargs,
        )

    def reconcile_active_agent_runs(self, *, owner: Optional[str] = None, limit: int = 500) -> list[dict[str, Any]]:
        rows = self.registry.list_runs(owner=owner, active=True, limit=limit)
        updated: list[dict[str, Any]] = []
        for run in rows:
            if run.get("run_type") != "agent":
                continue
            changed = self.get_for_run(run).reconcile(run, owner=owner)
            if changed:
                updated.append(changed)
        return updated


_DEFAULT_MANAGER: RunExecutorManager | None = None


def get_run_executor_manager(registry: Optional[RunRegistry] = None) -> RunExecutorManager:
    global _DEFAULT_MANAGER
    if registry is not None:
        return RunExecutorManager(registry)
    if _DEFAULT_MANAGER is None:
        _DEFAULT_MANAGER = RunExecutorManager()
    return _DEFAULT_MANAGER
