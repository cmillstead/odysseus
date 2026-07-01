"""Unified long-running Runs routes."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.runs import RunRegistry, get_run_executor_manager, get_run_registry
from services.runs.registry import ACTIVE_STATUSES
from src.auth_helpers import get_current_user


class SendToBackgroundRequest(BaseModel):
    title: Optional[str] = None
    objective: Optional[str] = None


class CreateRunRequest(BaseModel):
    title: Optional[str] = None
    objective: Optional[str] = None
    executor: str = "local_agent"
    session_id: Optional[str] = None
    parent_run_id: Optional[str] = None
    model: Optional[str] = None
    autonomy: str = "review_gated"
    metadata: Optional[dict[str, Any]] = None


class RunInputRequest(BaseModel):
    content: str
    input_type: str = "user"


class CreateSubrunRequest(BaseModel):
    title: Optional[str] = None
    objective: Optional[str] = None
    executor: Optional[str] = None
    session_id: Optional[str] = None
    model: Optional[str] = None
    autonomy: str = "review_gated"
    metadata: Optional[dict[str, Any]] = None


def setup_run_routes(task_scheduler=None, research_handler=None, registry: Optional[RunRegistry] = None) -> APIRouter:
    router = APIRouter(tags=["runs"])
    runs = registry or get_run_registry()
    executors = get_run_executor_manager(runs)

    def _owner(request: Request):
        return get_current_user(request)

    def _sync_known_sources(owner: Optional[str] = None):
        # Sync existing executor state into the ledger. Each adapter is
        # idempotent, so polling the Runs panel is safe.
        try:
            runs.sync_background_jobs()
        except Exception:
            pass
        try:
            runs.sync_recent_task_runs(owner=owner, limit=120)
        except Exception:
            pass
        try:
            active = getattr(research_handler, "_active_tasks", {}) if research_handler else {}
            for session_id, entry in list(active.items()):
                if owner and entry.get("owner") != owner:
                    continue
                runs.sync_research_entry(
                    session_id,
                    entry,
                    owner=entry.get("owner"),
                    model=entry.get("model"),
                    category=entry.get("category"),
                )
        except Exception:
            pass
        try:
            executors.reconcile_active_agent_runs(owner=owner)
        except Exception:
            pass

    @router.get("/api/run-executors")
    async def list_run_executors():
        return {"executors": executors.describe()}

    @router.post("/api/runs")
    async def create_run(request: Request, body: CreateRunRequest):
        owner = _owner(request)
        if body.executor not in executors.executors:
            raise HTTPException(400, "Unsupported run executor")
        if body.parent_run_id:
            parent = runs.get_run(body.parent_run_id, owner=owner)
            if not parent:
                raise HTTPException(404, "Parent run not found")
        title = body.title or ("Hermes sandbox run" if body.executor == "sandbox_agent" else "Local agent run")
        row = executors.launch(
            executor=body.executor or "local_agent",
            title=title,
            objective=body.objective,
            owner=owner,
            session_id=body.session_id,
            parent_run_id=body.parent_run_id,
            model=body.model,
            autonomy=body.autonomy,
            metadata=body.metadata,
        )
        return {"ok": True, "run": row}

    @router.get("/api/runs")
    async def list_runs(
        request: Request,
        status: Optional[str] = None,
        run_type: Optional[str] = None,
        active: bool = False,
        limit: int = 100,
    ):
        owner = _owner(request)
        _sync_known_sources(owner)
        rows = runs.list_runs(owner=owner, status=status, run_type=run_type, active=active, limit=limit)
        active_count = sum(1 for row in rows if row.get("status") in ACTIVE_STATUSES)
        return {"runs": rows, "count": len(rows), "active_count": active_count}

    @router.get("/api/runs/{run_id}")
    async def get_run(request: Request, run_id: str):
        owner = _owner(request)
        _sync_known_sources(owner)
        row = runs.get_run(run_id, owner=owner)
        if not row:
            raise HTTPException(404, "Run not found")
        return row

    @router.get("/api/runs/{run_id}/events")
    async def get_run_events(request: Request, run_id: str, limit: int = 500):
        owner = _owner(request)
        rows = runs.list_events(run_id, owner=owner, limit=limit)
        if rows is None:
            raise HTTPException(404, "Run not found")
        return {"events": rows, "count": len(rows)}

    @router.get("/api/runs/{run_id}/stream")
    async def stream_run_events(request: Request, run_id: str):
        owner = _owner(request)
        if not runs.get_run(run_id, owner=owner):
            raise HTTPException(404, "Run not found")

        async def _stream():
            seen: set[str] = set()
            heartbeat = 0
            while True:
                events = runs.list_events(run_id, owner=owner, limit=1000)
                if events is None:
                    yield "event: error\ndata: {\"error\":\"Run not found\"}\n\n"
                    return
                for event in events:
                    event_id = event.get("id")
                    if event_id in seen:
                        continue
                    seen.add(event_id)
                    yield f"id: {event_id}\nevent: run_event\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                row = runs.get_run(run_id, owner=owner)
                if row and row.get("status") not in ACTIVE_STATUSES:
                    yield f"event: run_snapshot\ndata: {json.dumps(row, ensure_ascii=False)}\n\n"
                    return
                if await request.is_disconnected():
                    return
                heartbeat += 1
                yield f": heartbeat {heartbeat} {int(time.time())}\n\n"
                await asyncio.sleep(1.5)

        return StreamingResponse(_stream(), media_type="text/event-stream")

    @router.post("/api/runs/{run_id}/cancel")
    async def cancel_run(request: Request, run_id: str):
        owner = _owner(request)
        row = runs.get_run(run_id, owner=owner)
        if not row:
            raise HTTPException(404, "Run not found")
        ok = False
        external_type = row.get("external_type")
        external_id = row.get("external_id")
        meta = row.get("metadata") or {}

        if row.get("run_type") == "agent":
            result = executors.get_for_run(row).cancel(row, owner=owner)
            return result.to_response()
        elif external_type == "bg_job" and external_id:
            try:
                from src import bg_jobs
                ok = bool(bg_jobs.kill(external_id))
            except Exception:
                ok = False
        elif external_type == "research_session":
            try:
                target = external_id or row.get("session_id")
                ok = bool(research_handler.cancel_research(target)) if research_handler and target else False
            except Exception:
                ok = False
        elif external_type == "task_run":
            try:
                task_id = meta.get("task_id")
                ok = bool(await task_scheduler.stop_task(task_id)) if task_scheduler and task_id else False
            except Exception:
                ok = False

        updated = runs.update_run(
            run_id,
            owner=owner,
            status="cancelled",
            current_step="Cancelled" if ok else "Cancellation requested",
            event_type="cancel",
            event_message="Run cancelled" if ok else "Cancellation requested",
        )
        return {"ok": True, "adapter_cancelled": ok, "run": updated}

    @router.post("/api/runs/{run_id}/pause")
    async def pause_run(request: Request, run_id: str):
        owner = _owner(request)
        row = runs.get_run(run_id, owner=owner)
        if not row:
            raise HTTPException(404, "Run not found")
        if row.get("run_type") == "agent":
            result = executors.get_for_run(row).pause(row, owner=owner)
            if not result.supported:
                raise HTTPException(409, result.message)
            return result.to_response()
        updated = runs.update_run(
            run_id,
            owner=owner,
            status="paused",
            current_step="Paused",
            event_type="pause",
            event_message="Run paused",
        )
        return {"ok": True, "run": updated}

    @router.post("/api/runs/{run_id}/resume")
    async def resume_run(request: Request, run_id: str):
        owner = _owner(request)
        row = runs.get_run(run_id, owner=owner)
        if not row:
            raise HTTPException(404, "Run not found")
        if row.get("run_type") == "agent":
            result = executors.get_for_run(row).resume(row, owner=owner)
            if not result.ok:
                return result.to_response()
            return result.to_response()
        updated = runs.update_run(
            run_id,
            owner=owner,
            status="running",
            current_step="Resumed",
            event_type="resume",
            event_message="Run resumed",
        )
        return {"ok": True, "run": updated}

    @router.post("/api/runs/{run_id}/inputs")
    async def append_run_input(request: Request, run_id: str, body: RunInputRequest):
        owner = _owner(request)
        row = runs.get_run(run_id, owner=owner)
        if not row:
            raise HTTPException(404, "Run not found")
        content = (body.content or "").strip()
        if not content:
            raise HTTPException(400, "Input content is required")
        result = executors.get_for_run(row).append_input(row, content=content, owner=owner, input_type=body.input_type)
        return result.to_response()

    @router.post("/api/runs/{run_id}/subruns")
    async def create_subrun(request: Request, run_id: str, body: CreateSubrunRequest):
        owner = _owner(request)
        parent = runs.get_run(run_id, owner=owner)
        if not parent:
            raise HTTPException(404, "Run not found")
        if body.executor and body.executor not in executors.executors:
            raise HTTPException(400, "Unsupported run executor")
        title = body.title or f"Subrun: {parent.get('title') or run_id[:8]}"
        child = executors.create_subrun(
            parent,
            executor=body.executor,
            title=title,
            objective=body.objective,
            session_id=body.session_id or parent.get("session_id"),
            model=body.model or parent.get("model"),
            autonomy=body.autonomy,
            metadata=body.metadata,
        )
        runs.append_event(
            parent["id"],
            "subrun_created",
            f"Subrun created: {title}",
            payload={"child_run_id": child.get("id"), "executor": child.get("executor")},
            owner=owner,
        )
        return {"ok": True, "run": child, "parent": runs.get_run(parent["id"], owner=owner)}

    @router.post("/api/runs/{run_id}/approvals/{approval_id}/approve")
    async def approve_run_action(request: Request, run_id: str, approval_id: str):
        owner = _owner(request)
        row = runs.get_run(run_id, owner=owner)
        if not row:
            raise HTTPException(404, "Run not found")
        result = executors.get_for_run(row).resolve_approval(row, approval_id, owner=owner, approved=True)
        if not result.ok:
            raise HTTPException(404, "Approval not found")
        approval = next((event for event in (result.run or {}).get("events", []) if event.get("approval_id") == approval_id), None)
        return {"ok": True, "approval": approval, "run": result.run}

    @router.post("/api/runs/{run_id}/approvals/{approval_id}/reject")
    async def reject_run_action(request: Request, run_id: str, approval_id: str):
        owner = _owner(request)
        row = runs.get_run(run_id, owner=owner)
        if not row:
            raise HTTPException(404, "Run not found")
        result = executors.get_for_run(row).resolve_approval(row, approval_id, owner=owner, approved=False)
        if not result.ok:
            raise HTTPException(404, "Approval not found")
        approval = next((event for event in (result.run or {}).get("events", []) if event.get("approval_id") == approval_id), None)
        return {"ok": True, "approval": approval, "run": result.run}

    @router.post("/api/runs/chat/{session_id}/send-to-background")
    async def send_chat_to_background(request: Request, session_id: str, body: SendToBackgroundRequest):
        owner = _owner(request)
        title = body.title or "Background agent run"
        row = executors.launch(
            executor="local_agent",
            title=title,
            objective=body.objective,
            owner=owner,
            session_id=session_id,
            metadata={"source": "send_to_background"},
        )
        runs.append_event(row["id"], "progress", "Chat session registered for durable background follow-up", owner=owner)
        return {"ok": True, "run": runs.get_run(row["id"], owner=owner)}

    return router
