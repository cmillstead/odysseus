"""Durable registry for long-running Odysseus work.

This layer is intentionally adapter-oriented: existing executors continue to
own execution, while this service owns normalized visibility, timeline events,
artifacts, and approval state.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from core.database import (
    RunArtifact,
    RunEvent,
    RunRecord,
    ScheduledTask,
    Session,
    SessionLocal,
    TaskRun,
    utcnow_naive,
)

logger = logging.getLogger(__name__)

RUN_TYPES = {
    "agent",
    "background_shell",
    "research",
    "scheduled_task",
    "skill_audit",
    "learning_review",
}
RUN_STATUSES = {
    "queued",
    "running",
    "paused",
    "waiting_for_approval",
    "blocked",
    "succeeded",
    "failed",
    "cancelled",
}
ACTIVE_STATUSES = {"queued", "running", "paused", "waiting_for_approval", "blocked"}
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


def _now() -> datetime:
    return utcnow_naive()


def _iso(dt: Any) -> Optional[str]:
    if not dt:
        return None
    if isinstance(dt, (int, float)):
        try:
            return datetime.fromtimestamp(float(dt), timezone.utc).replace(tzinfo=None).isoformat() + "Z"
        except Exception:
            return None
    if isinstance(dt, datetime):
        return dt.isoformat() + ("Z" if dt.tzinfo is None else "")
    return str(dt)


def _json_dumps(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return json.dumps({"value": str(value)}, ensure_ascii=False)


def _json_loads(value: Any, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _clean_string(value: Any, limit: int = 4000) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    return text[:limit]


def normalize_status(status: Any, default: str = "running") -> str:
    text = str(status or default).strip().lower()
    mapping = {
        "done": "succeeded",
        "success": "succeeded",
        "completed": "succeeded",
        "complete": "succeeded",
        "error": "failed",
        "failed": "failed",
        "aborted": "cancelled",
        "cancelled": "cancelled",
        "canceled": "cancelled",
        "killed": "cancelled",
        "skipped": "cancelled",
        "pending": "queued",
        "in_progress": "running",
        "pause": "paused",
        "paused": "paused",
        "approval": "waiting_for_approval",
        "waiting": "waiting_for_approval",
    }
    text = mapping.get(text, text)
    return text if text in RUN_STATUSES else default


def _task_status(status: Any) -> str:
    return normalize_status(status, default="running")


class RunRegistry:
    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _run_to_dict(self, run: RunRecord, *, include_counts: bool = True) -> dict[str, Any]:
        data = {
            "id": run.id,
            "owner": run.owner,
            "run_type": run.run_type,
            "status": run.status,
            "title": run.title,
            "objective": run.objective,
            "origin": run.origin,
            "executor": run.executor,
            "backend": run.backend,
            "model": run.model,
            "session_id": run.session_id,
            "parent_run_id": run.parent_run_id,
            "external_type": run.external_type,
            "external_id": run.external_id,
            "current_step": run.current_step,
            "summary": run.summary,
            "error": run.error,
            "approval_state": run.approval_state,
            "metadata": _json_loads(run.meta_data, {}),
            "created_at": _iso(run.created_at),
            "updated_at": _iso(run.updated_at),
            "started_at": _iso(run.started_at),
            "finished_at": _iso(run.finished_at),
        }
        if include_counts:
            try:
                data["event_count"] = len(getattr(run, "events", []) or [])
                data["artifact_count"] = len(getattr(run, "artifacts", []) or [])
            except Exception:
                pass
        return data

    def _event_to_dict(self, event: RunEvent) -> dict[str, Any]:
        return {
            "id": event.id,
            "run_id": event.run_id,
            "owner": event.owner,
            "event_type": event.event_type,
            "message": event.message,
            "payload": _json_loads(event.payload, {}),
            "approval_id": event.approval_id,
            "approval_status": event.approval_status,
            "created_at": _iso(event.created_at),
        }

    def _artifact_to_dict(self, artifact: RunArtifact) -> dict[str, Any]:
        return {
            "id": artifact.id,
            "run_id": artifact.run_id,
            "owner": artifact.owner,
            "artifact_type": artifact.artifact_type,
            "name": artifact.name,
            "uri": artifact.uri,
            "path": artifact.path,
            "mime_type": artifact.mime_type,
            "metadata": _json_loads(artifact.meta_data, {}),
            "created_at": _iso(artifact.created_at),
        }

    # ------------------------------------------------------------------
    # Core writes
    # ------------------------------------------------------------------

    def create_run(
        self,
        *,
        run_type: str,
        title: str,
        owner: Optional[str] = None,
        objective: Optional[str] = None,
        origin: Optional[str] = None,
        executor: Optional[str] = None,
        backend: Optional[str] = None,
        model: Optional[str] = None,
        session_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        external_type: Optional[str] = None,
        external_id: Optional[str] = None,
        status: str = "queued",
        current_step: Optional[str] = None,
        summary: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if run_type not in RUN_TYPES:
            raise ValueError(f"Unsupported run_type: {run_type}")
        status = normalize_status(status, default="queued")
        now = _now()
        run = RunRecord(
            id=uuid.uuid4().hex,
            owner=owner or None,
            run_type=run_type,
            status=status,
            title=_clean_string(title, 240) or "Untitled Run",
            objective=_clean_string(objective),
            origin=_clean_string(origin, 120),
            executor=_clean_string(executor, 120),
            backend=_clean_string(backend, 120),
            model=_clean_string(model, 240),
            session_id=session_id or None,
            parent_run_id=parent_run_id or None,
            external_type=_clean_string(external_type, 120),
            external_id=_clean_string(external_id, 240),
            current_step=_clean_string(current_step, 4000),
            summary=_clean_string(summary),
            error=_clean_string(error, 2000),
            approval_state="waiting" if status == "waiting_for_approval" else "none",
            meta_data=_json_dumps(metadata or {}),
            started_at=now if status == "running" else None,
            finished_at=now if status in TERMINAL_STATUSES else None,
        )
        db = self.session_factory()
        try:
            db.add(run)
            db.commit()
            self.append_event(
                run.id,
                "run_created",
                f"{run.title} created",
                payload={"status": run.status, "run_type": run.run_type},
                owner=run.owner,
            )
            return self.get_run(run.id, owner=owner) or self._run_to_dict(run)
        finally:
            db.close()

    def ensure_run(
        self,
        *,
        run_type: str,
        title: str,
        owner: Optional[str] = None,
        external_type: Optional[str] = None,
        external_id: Optional[str] = None,
        **updates: Any,
    ) -> dict[str, Any]:
        if not external_type or not external_id:
            return self.create_run(
                run_type=run_type,
                title=title,
                owner=owner,
                external_type=external_type,
                external_id=external_id,
                **updates,
            )
        db = self.session_factory()
        try:
            q = db.query(RunRecord).filter(
                RunRecord.external_type == external_type,
                RunRecord.external_id == str(external_id),
            )
            if owner:
                q = q.filter(RunRecord.owner == owner)
            run = q.order_by(RunRecord.created_at.desc()).first()
            if not run:
                db.close()
                return self.create_run(
                    run_type=run_type,
                    title=title,
                    owner=owner,
                    external_type=external_type,
                    external_id=str(external_id),
                    **updates,
                )
            changed = False
            fields = {
                "title": title,
                "run_type": run_type,
                "owner": owner or run.owner,
                "objective": updates.get("objective"),
                "origin": updates.get("origin"),
                "executor": updates.get("executor"),
                "backend": updates.get("backend"),
                "model": updates.get("model"),
                "session_id": updates.get("session_id"),
                "parent_run_id": updates.get("parent_run_id"),
                "current_step": updates.get("current_step"),
            }
            for key, value in fields.items():
                if value is None:
                    continue
                clean = _clean_string(value, 4000)
                if getattr(run, key) != clean:
                    setattr(run, key, clean)
                    changed = True
            if updates.get("metadata") is not None:
                current = _json_loads(run.meta_data, {}) or {}
                current.update(updates.get("metadata") or {})
                run.meta_data = _json_dumps(current)
                changed = True
            if updates.get("status") is not None:
                status = normalize_status(updates.get("status"), default=run.status)
                if run.status != status:
                    run.status = status
                    if status == "running" and not run.started_at:
                        run.started_at = _now()
                    if status in TERMINAL_STATUSES and not run.finished_at:
                        run.finished_at = _now()
                    changed = True
            if updates.get("summary") is not None:
                run.summary = _clean_string(updates.get("summary"))
                changed = True
            if updates.get("error") is not None:
                run.error = _clean_string(updates.get("error"), 2000)
                changed = True
            if changed:
                run.updated_at = _now()
                db.commit()
            return self._run_to_dict(run)
        finally:
            try:
                db.close()
            except Exception:
                pass

    def update_run(
        self,
        run_id: str,
        *,
        owner: Optional[str] = None,
        status: Optional[str] = None,
        current_step: Optional[str] = None,
        summary: Optional[str] = None,
        error: Optional[str] = None,
        model: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        event_type: str = "status",
        event_message: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        db = self.session_factory()
        try:
            run = self._owned_query(db, owner).filter(RunRecord.id == run_id).first()
            if not run:
                return None
            old_status = run.status
            if status is not None:
                run.status = normalize_status(status, default=run.status)
                if run.status == "running" and not run.started_at:
                    run.started_at = _now()
                if run.status in TERMINAL_STATUSES and not run.finished_at:
                    run.finished_at = _now()
            if current_step is not None:
                run.current_step = _clean_string(current_step)
            if summary is not None:
                run.summary = _clean_string(summary)
            if error is not None:
                run.error = _clean_string(error, 2000)
            if model is not None:
                run.model = _clean_string(model, 240)
            if metadata is not None:
                current = _json_loads(run.meta_data, {}) or {}
                current.update(metadata)
                run.meta_data = _json_dumps(current)
            run.updated_at = _now()
            db.commit()
            if status is not None or event_message:
                payload = {"old_status": old_status, "status": run.status}
                self.append_event(
                    run.id,
                    event_type,
                    event_message or f"Status changed to {run.status}",
                    payload=payload,
                    owner=run.owner,
                )
            return self._run_to_dict(run)
        finally:
            db.close()

    def append_event(
        self,
        run_id: str,
        event_type: str,
        message: Optional[str] = None,
        *,
        payload: Optional[dict[str, Any]] = None,
        approval_id: Optional[str] = None,
        approval_status: Optional[str] = None,
        owner: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        db = self.session_factory()
        try:
            run = db.query(RunRecord).filter(RunRecord.id == run_id).first()
            if not run:
                return None
            event = RunEvent(
                id=uuid.uuid4().hex,
                run_id=run.id,
                owner=owner if owner is not None else run.owner,
                event_type=_clean_string(event_type, 120) or "event",
                message=_clean_string(message),
                payload=_json_dumps(payload or {}),
                approval_id=_clean_string(approval_id, 120),
                approval_status=_clean_string(approval_status, 60),
            )
            db.add(event)
            run.updated_at = _now()
            db.commit()
            return self._event_to_dict(event)
        finally:
            db.close()

    def add_artifact(
        self,
        run_id: str,
        *,
        name: str,
        artifact_type: str = "file",
        owner: Optional[str] = None,
        uri: Optional[str] = None,
        path: Optional[str] = None,
        mime_type: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        db = self.session_factory()
        try:
            run = db.query(RunRecord).filter(RunRecord.id == run_id).first()
            if not run:
                return None
            existing = None
            if path:
                existing = (
                    db.query(RunArtifact)
                    .filter(RunArtifact.run_id == run_id, RunArtifact.path == path)
                    .first()
                )
            elif uri:
                existing = (
                    db.query(RunArtifact)
                    .filter(RunArtifact.run_id == run_id, RunArtifact.uri == uri)
                    .first()
                )
            if existing:
                return self._artifact_to_dict(existing)
            artifact = RunArtifact(
                id=uuid.uuid4().hex,
                run_id=run.id,
                owner=owner if owner is not None else run.owner,
                artifact_type=_clean_string(artifact_type, 80) or "file",
                name=_clean_string(name, 240) or "Artifact",
                uri=_clean_string(uri, 2000),
                path=_clean_string(path, 2000),
                mime_type=_clean_string(mime_type, 120),
                meta_data=_json_dumps(metadata or {}),
            )
            db.add(artifact)
            run.updated_at = _now()
            db.commit()
            self.append_event(run.id, "artifact", f"Artifact added: {artifact.name}", payload={"artifact_id": artifact.id})
            return self._artifact_to_dict(artifact)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def _owned_query(self, db, owner: Optional[str]):
        q = db.query(RunRecord)
        if owner:
            q = q.filter(RunRecord.owner == owner)
        return q

    def list_runs(
        self,
        *,
        owner: Optional[str] = None,
        status: Optional[str] = None,
        run_type: Optional[str] = None,
        active: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit or 100), 500))
        db = self.session_factory()
        try:
            q = self._owned_query(db, owner)
            if active:
                q = q.filter(RunRecord.status.in_(tuple(ACTIVE_STATUSES)))
            elif status:
                q = q.filter(RunRecord.status == normalize_status(status, default=status))
            if run_type:
                q = q.filter(RunRecord.run_type == run_type)
            rows = q.order_by(RunRecord.updated_at.desc(), RunRecord.created_at.desc()).limit(limit).all()
            return [self._run_to_dict(row) for row in rows]
        finally:
            db.close()

    def get_run(self, run_id: str, *, owner: Optional[str] = None) -> Optional[dict[str, Any]]:
        db = self.session_factory()
        try:
            run = self._owned_query(db, owner).filter(RunRecord.id == run_id).first()
            if not run:
                return None
            data = self._run_to_dict(run)
            data["events"] = [self._event_to_dict(e) for e in run.events]
            data["artifacts"] = [self._artifact_to_dict(a) for a in run.artifacts]
            children = (
                self._owned_query(db, owner)
                .filter(RunRecord.parent_run_id == run_id)
                .order_by(RunRecord.created_at.asc())
                .all()
            )
            data["children"] = [self._run_to_dict(child, include_counts=False) for child in children]
            return data
        finally:
            db.close()

    def list_events(self, run_id: str, *, owner: Optional[str] = None, limit: int = 500) -> Optional[list[dict[str, Any]]]:
        limit = max(1, min(int(limit or 500), 1000))
        db = self.session_factory()
        try:
            run = self._owned_query(db, owner).filter(RunRecord.id == run_id).first()
            if not run:
                return None
            rows = (
                db.query(RunEvent)
                .filter(RunEvent.run_id == run_id)
                .order_by(RunEvent.created_at.asc())
                .limit(limit)
                .all()
            )
            return [self._event_to_dict(row) for row in rows]
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Approvals
    # ------------------------------------------------------------------

    def create_approval(
        self,
        run_id: str,
        *,
        title: str,
        payload: Optional[dict[str, Any]] = None,
        owner: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        approval_id = uuid.uuid4().hex
        self.update_run(
            run_id,
            owner=owner,
            status="waiting_for_approval",
            current_step=title,
            metadata={"last_approval_id": approval_id},
            event_type="approval_requested",
            event_message=title,
        )
        return self.append_event(
            run_id,
            "approval_requested",
            title,
            payload=payload or {},
            approval_id=approval_id,
            approval_status="pending",
            owner=owner,
        )

    def resolve_approval(
        self,
        run_id: str,
        approval_id: str,
        *,
        owner: Optional[str] = None,
        approved: bool,
    ) -> Optional[dict[str, Any]]:
        db = self.session_factory()
        try:
            run = self._owned_query(db, owner).filter(RunRecord.id == run_id).first()
            if not run:
                return None
            event = (
                db.query(RunEvent)
                .filter(RunEvent.run_id == run_id, RunEvent.approval_id == approval_id)
                .order_by(RunEvent.created_at.desc())
                .first()
            )
            if not event:
                return None
            event.approval_status = "approved" if approved else "rejected"
            run.approval_state = event.approval_status
            if run.status == "waiting_for_approval":
                run.status = "running" if approved else "blocked"
                if not run.started_at:
                    run.started_at = _now()
            run.updated_at = _now()
            db.commit()
            result = self._event_to_dict(event)
        finally:
            db.close()
        self.append_event(
            run_id,
            "approval_resolved",
            "Approval accepted" if approved else "Approval rejected",
            payload={"approval_id": approval_id, "approved": approved},
            owner=owner,
        )
        return result

    # ------------------------------------------------------------------
    # Existing executor adapters
    # ------------------------------------------------------------------

    def sync_background_job(self, rec: dict[str, Any], *, owner: Optional[str] = None) -> Optional[dict[str, Any]]:
        if not isinstance(rec, dict) or not rec.get("id"):
            return None
        session_id = rec.get("session_id")
        resolved_owner = owner
        if resolved_owner is None and session_id:
            db = self.session_factory()
            try:
                sess = db.query(Session).filter(Session.id == session_id).first()
                if sess:
                    resolved_owner = sess.owner
            finally:
                db.close()
        status = normalize_status(rec.get("status"), default="running")
        if rec.get("killed"):
            status = "cancelled"
        title = f"Background shell: {str(rec.get('command') or '').splitlines()[0][:80] or rec['id']}"
        run = self.ensure_run(
            run_type="background_shell",
            title=title,
            owner=resolved_owner,
            objective=rec.get("command"),
            origin="agent:bash",
            executor="bg_jobs",
            session_id=session_id,
            external_type="bg_job",
            external_id=rec["id"],
            status=status,
            current_step="Running shell command" if status == "running" else f"Exit code {rec.get('exit_code')}",
            error="Background shell failed" if status == "failed" else None,
            metadata={
                "pid": rec.get("pid"),
                "exit_code": rec.get("exit_code"),
                "log_path": rec.get("log_path"),
                "started_at_unix": rec.get("started_at"),
                "ended_at_unix": rec.get("ended_at"),
                "followed_up": rec.get("followed_up"),
            },
        )
        if rec.get("log_path"):
            self.add_artifact(
                run["id"],
                name=f"{rec['id']}.log",
                artifact_type="log",
                path=rec.get("log_path"),
                owner=resolved_owner,
            )
        return run

    def sync_background_jobs(self, *, owner: Optional[str] = None) -> list[dict[str, Any]]:
        try:
            from src import bg_jobs
            jobs = bg_jobs.refresh()
        except Exception:
            logger.debug("Background job sync failed", exc_info=True)
            return []
        out = []
        for rec in jobs.values():
            run = self.sync_background_job(rec, owner=owner)
            if run and (not owner or run.get("owner") == owner):
                out.append(run)
        return out

    def adopt_task_run(self, task_run: TaskRun, task: ScheduledTask) -> Optional[dict[str, Any]]:
        if not task_run or not task:
            return None
        status = _task_status(task_run.status)
        title = f"Task: {task.name or task.id}"
        run = self.ensure_run(
            run_type="scheduled_task",
            title=title,
            owner=task.owner,
            objective=task.prompt,
            origin=f"task:{task.trigger_type or 'schedule'}",
            executor="task_scheduler",
            model=task_run.model or task.model,
            session_id=task.session_id,
            external_type="task_run",
            external_id=task_run.id,
            status=status,
            current_step=task_run.result if status in ACTIVE_STATUSES else None,
            summary=task_run.result if status == "succeeded" else None,
            error=task_run.error if status in {"failed", "cancelled"} else None,
            metadata={
                "task_id": task.id,
                "task_name": task.name,
                "task_type": task.task_type,
                "action": task.action,
                "task_status": task_run.status,
                "steps": _json_loads(task_run.steps, []),
            },
        )
        return run

    def sync_recent_task_runs(self, *, owner: Optional[str] = None, limit: int = 100) -> list[dict[str, Any]]:
        db = self.session_factory()
        try:
            q = db.query(TaskRun, ScheduledTask).join(ScheduledTask, TaskRun.task_id == ScheduledTask.id)
            if owner:
                q = q.filter(ScheduledTask.owner == owner)
            rows = q.order_by(TaskRun.started_at.desc()).limit(max(1, min(limit, 300))).all()
            return [r for r in (self.adopt_task_run(run, task) for run, task in rows) if r]
        except Exception:
            logger.debug("Task run sync failed", exc_info=True)
            return []
        finally:
            db.close()

    def sync_research_entry(
        self,
        session_id: str,
        entry: dict[str, Any],
        *,
        owner: Optional[str] = None,
        model: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        if not session_id or not isinstance(entry, dict):
            return None
        status = normalize_status(entry.get("status"), default="running")
        query = entry.get("query") or "Research"
        progress = entry.get("progress") or {}
        step = progress.get("message") if isinstance(progress, dict) else None
        if not step and status == "running":
            step = "Research running"
        return self.ensure_run(
            run_type="research",
            title=f"Research: {str(query)[:80]}",
            owner=owner or entry.get("owner"),
            objective=query,
            origin="research_panel",
            executor="research_handler",
            model=model or entry.get("model"),
            session_id=session_id,
            external_type="research_session",
            external_id=session_id,
            status=status,
            current_step=step,
            summary=entry.get("result") if status == "succeeded" else None,
            error=entry.get("result") if status == "failed" else None,
            metadata={
                "category": category or entry.get("category"),
                "started_at_unix": entry.get("started_at"),
                "progress": progress,
            },
        )


_DEFAULT_REGISTRY: RunRegistry | None = None


def get_run_registry() -> RunRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = RunRegistry()
    return _DEFAULT_REGISTRY
