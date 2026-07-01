"""Routes for staged native learning proposals."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from services.memory.learning_review import (
    LearningProposalStore,
    apply_proposal,
    proposal_diff,
    preview_hermes_import,
    stage_hermes_import,
    stage_skill_curations,
)
from services.runs import get_run_registry
from src.auth_helpers import get_current_user


def setup_learning_routes(memory_manager, memory_vector, skills_manager) -> APIRouter:
    router = APIRouter(prefix="/api/learning", tags=["learning"])
    store = LearningProposalStore()

    def _owner(request: Request):
        return get_current_user(request)

    @router.get("/pending")
    async def list_pending(request: Request):
        owner = _owner(request)
        rows = store.list_pending(owner=owner)
        return {"proposals": rows, "count": len(rows)}

    async def _json_body(request: Request) -> dict:
        try:
            data = await request.json()
        except Exception:
            data = {}
        return data if isinstance(data, dict) else {}

    @router.get("/pending/{proposal_id}/diff")
    async def get_diff(request: Request, proposal_id: str):
        owner = _owner(request)
        row = store.get(proposal_id, owner=owner)
        if not row or row.get("status") != "pending":
            raise HTTPException(404, "Proposal not found")
        diff = row.get("diff") or proposal_diff(row, memory_manager, skills_manager)
        return {"id": proposal_id, "diff": diff}

    @router.post("/pending/{proposal_id}/approve")
    async def approve(request: Request, proposal_id: str):
        owner = _owner(request)
        row = store.get(proposal_id, owner=owner)
        if not row or row.get("status") != "pending":
            raise HTTPException(404, "Proposal not found")
        try:
            result = apply_proposal(row, memory_manager, memory_vector, skills_manager)
        except KeyError as e:
            raise HTTPException(404, str(e)) from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        updated = store.update_status(proposal_id, owner, "approved", result=result)
        try:
            registry = get_run_registry()
            run = registry.create_run(
                run_type="learning_review",
                title=f"Approved learning: {row.get('summary') or proposal_id}",
                owner=owner,
                objective=row.get("summary"),
                origin=row.get("source") or "learning-review",
                executor="learning_review",
                external_type="learning_proposal",
                external_id=proposal_id,
                status="succeeded",
                summary=row.get("summary"),
                metadata={"proposal_id": proposal_id, "kind": row.get("kind"), "action": row.get("action"), "result": result},
            )
            registry.append_event(run["id"], "approval_resolved", "Learning proposal approved", payload={"proposal_id": proposal_id}, owner=owner)
        except Exception:
            pass
        return {"ok": True, "proposal": updated, "result": result}

    @router.post("/pending/approve-all")
    async def approve_all(request: Request):
        owner = _owner(request)
        rows = store.list_pending(owner=owner)
        results = []
        approved = 0
        for row in rows:
            try:
                result = apply_proposal(row, memory_manager, memory_vector, skills_manager)
                updated = store.update_status(row["id"], owner, "approved", result=result)
                results.append({"id": row["id"], "ok": True, "proposal": updated, "result": result})
                approved += 1
            except (KeyError, ValueError) as e:
                results.append({"id": row.get("id"), "ok": False, "error": str(e)})
        try:
            registry = get_run_registry()
            run = registry.create_run(
                run_type="learning_review",
                title="Approved pending learning",
                owner=owner,
                objective="Approve all pending memory and skill proposals",
                origin="brain:pending",
                executor="learning_review",
                external_type="learning_bulk_approval",
                external_id=f"{owner or 'shared'}:{len(rows)}:{approved}",
                status="succeeded" if approved == len(rows) else "failed",
                summary=f"{approved}/{len(rows)} proposal(s) approved",
                metadata={"approved": approved, "total": len(rows), "results": results},
            )
            registry.append_event(run["id"], "approval_resolved", "Bulk learning approval completed", payload={"approved": approved, "total": len(rows)}, owner=owner)
        except Exception:
            pass
        return {"ok": True, "approved": approved, "total": len(rows), "results": results}

    @router.post("/pending/{proposal_id}/reject")
    async def reject(request: Request, proposal_id: str):
        owner = _owner(request)
        row = store.get(proposal_id, owner=owner)
        if not row or row.get("status") != "pending":
            raise HTTPException(404, "Proposal not found")
        updated = store.update_status(proposal_id, owner, "rejected", result={"applied": False})
        try:
            registry = get_run_registry()
            run = registry.create_run(
                run_type="learning_review",
                title=f"Rejected learning: {row.get('summary') or proposal_id}",
                owner=owner,
                objective=row.get("summary"),
                origin=row.get("source") or "learning-review",
                executor="learning_review",
                external_type="learning_proposal",
                external_id=proposal_id,
                status="cancelled",
                summary=row.get("summary"),
                metadata={"proposal_id": proposal_id, "kind": row.get("kind"), "action": row.get("action")},
            )
            registry.append_event(run["id"], "approval_resolved", "Learning proposal rejected", payload={"proposal_id": proposal_id}, owner=owner)
        except Exception:
            pass
        return {"ok": True, "proposal": updated}

    @router.post("/pending/reject-all")
    async def reject_all(request: Request):
        owner = _owner(request)
        rows = store.list_pending(owner=owner)
        rejected = []
        for row in rows:
            updated = store.update_status(row["id"], owner, "rejected", result={"applied": False})
            rejected.append(updated or row)
        try:
            registry = get_run_registry()
            run = registry.create_run(
                run_type="learning_review",
                title="Rejected pending learning",
                owner=owner,
                objective="Reject all pending memory and skill proposals",
                origin="brain:pending",
                executor="learning_review",
                external_type="learning_bulk_rejection",
                external_id=f"{owner or 'shared'}:{len(rejected)}",
                status="cancelled",
                summary=f"{len(rejected)} proposal(s) rejected",
                metadata={"proposal_ids": [r.get("id") for r in rejected]},
            )
            registry.append_event(run["id"], "approval_resolved", "Bulk learning rejection completed", payload={"rejected": len(rejected)}, owner=owner)
        except Exception:
            pass
        return {"ok": True, "rejected": len(rejected), "total": len(rows), "proposals": rejected}

    @router.post("/curate")
    async def curate(request: Request):
        owner = _owner(request)
        data = await _json_body(request)
        dry_run = bool(data.get("dry_run", False))
        try:
            max_items = max(1, min(50, int(data.get("max_items", 20))))
        except (TypeError, ValueError):
            max_items = 20
        rows = stage_skill_curations(
            skills_manager,
            owner=owner,
            store=store,
            max_items=max_items,
            dry_run=dry_run,
        )
        try:
            registry = get_run_registry()
            run = registry.create_run(
                run_type="learning_review",
                title="Skill curation",
                owner=owner,
                objective="Review learned skills for archive candidates",
                origin="brain:curate",
                executor="learning_review",
                external_type="skill_curation",
                external_id=f"{owner or 'shared'}:{'dry' if dry_run else 'stage'}",
                status="succeeded",
                summary=f"{len(rows)} proposal(s) {'previewed' if dry_run else 'staged'}",
                metadata={"dry_run": dry_run, "proposal_ids": [r.get("id") for r in rows]},
            )
            registry.append_event(run["id"], "complete", "Skill curation completed", payload={"count": len(rows), "dry_run": dry_run}, owner=owner)
        except Exception:
            pass
        return {"ok": True, "dry_run": dry_run, "proposals": rows, "count": len(rows)}

    @router.post("/hermes/preview")
    async def hermes_preview(request: Request):
        owner = _owner(request)
        data = await _json_body(request)
        base_path = data.get("base_path") or "~/.hermes"
        source_name = data.get("source_name") or "hermes"
        result = preview_hermes_import(base_path, owner=owner, source_name=source_name)
        try:
            registry = get_run_registry()
            run = registry.create_run(
                run_type="learning_review",
                title="Hermes import preview",
                owner=owner,
                objective=f"Preview import from {base_path}",
                origin="brain:hermes-preview",
                executor="learning_review",
                external_type="hermes_import",
                external_id=f"{owner or 'shared'}:{base_path}:preview",
                status="succeeded",
                summary=f"{result.get('count', 0)} item(s) previewed",
                metadata={"base_path": base_path, "source_name": source_name, "count": result.get("count")},
            )
            registry.append_event(run["id"], "complete", "Hermes preview completed", payload={"count": result.get("count", 0)}, owner=owner)
        except Exception:
            pass
        return result

    @router.post("/hermes/stage")
    async def hermes_stage(request: Request):
        owner = _owner(request)
        data = await _json_body(request)
        base_path = data.get("base_path") or "~/.hermes"
        source_name = data.get("source_name") or "hermes"
        result = stage_hermes_import(base_path, owner=owner, source_name=source_name, store=store)
        try:
            registry = get_run_registry()
            proposals = result.get("proposals") or []
            run = registry.create_run(
                run_type="learning_review",
                title="Hermes import staged",
                owner=owner,
                objective=f"Stage import from {base_path}",
                origin="brain:hermes-stage",
                executor="learning_review",
                external_type="hermes_import",
                external_id=f"{owner or 'shared'}:{base_path}:stage",
                status="succeeded",
                summary=f"{len(proposals)} proposal(s) staged",
                metadata={"base_path": base_path, "source_name": source_name, "proposal_ids": [p.get("id") for p in proposals]},
            )
            registry.append_event(run["id"], "complete", "Hermes import staged", payload={"count": len(proposals)}, owner=owner)
        except Exception:
            pass
        return {"ok": True, **result}

    return router
