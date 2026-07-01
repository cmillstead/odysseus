# Project State

## Project Reference

See: .paul/PROJECT.md (updated 2026-07-01)

**Core value:** Contributors can navigate and safely change the backend because domain
logic lives in discoverable, right-sized modules — zero behavior change, no broken imports.
**Current focus:** v0.1 Backend Module Boundaries (Slice 2, multi-file domains) — grounded; ready to plan Phase 1.

## Current Position

Milestone: v0.1 Backend Module Boundaries
Phase: 1 of 3 — Low-risk domains (Documents, Auth) — **COMPLETE**; Phase 2 next
Plan: 01-01 (Documents, PR #3) + 01-02 (Auth, PR #4) both SHIPPED. Next: 02-01 (Calendar/Contacts).
Status: Phase 1 done (both low-risk domains merged) → GROUND/PLAN 02-01 (Calendar/Contacts, MEDIUM)
Last activity: 2026-07-01 — 01-02 Auth shipped: Codex clean, full suite 4265 passed / 0 new failures, PR #4 merged (`dcde7b1`)

Progress:
- Milestone: [█████░░░░░] 56% by domain (5 of 9 merged: email, gallery, research, document, auth)
- Phase 1: [██████████] 100% (2 of 2 plans complete)

## Loop Position

Current loop state:
```
PLAN ──▶ APPLY ──▶ UNIFY ──▶ SHIPPED
  ✓        ✓        ✓         ✓   [01-02 merged (PR #4) — Phase 1 COMPLETE; next: 02-01 Calendar/Contacts]
```

## Accumulated Context

### Decisions

| Decision | Impact |
|----------|--------|
| Fork-local is source of truth | `src/tools/` naming stays; upstream issues reference-only |
| v0.1 = finish Slice 1 + all Slice 2 | Defers agent_loop / src-layering / database to later milestones |
| `sys.modules` alias shim pattern | Preserves import paths + `mock.patch` targets across every move |
| One domain per PR | Atomic, reviewable, behavior-preserving slices |

### Deferred Issues

| Issue | Origin | Revisit |
|-------|--------|---------|
| `ai_interaction.py` decomposition (1,846 ln shared infra) | Grounding | v0.2.x milestone (NOT Slice 1) |
| Chat/Agent shape — bundle shell/codex/skills into routes/chat/ or leave flat | Grounding | Plan-time for 03-01 |
| Themed groupings (Calendar+Contacts, Model+Assistant+Copilot) — co-locate vs separate | Grounding | Plan-time for 02-01, 02-02 |
| Singleton "Other" bucket (23 files) grouping | Grounding | Optional v0.1.x pass |
| `implementation-spec-capability-gaps.md` (WS-0..25) | Feature roadmap, separate | After backend boundaries milestone |
| `test_auth_regressions.py` subset-run fragility — its `_ensure_stub`/`_auth_regressions_stubs` fixture assumes `core.auth` is pre-loaded; the auth shim (01-02) stopped pop-and-reimport from re-establishing it, so running the auth files as a NARROW subset now ImportErrors on `RESERVED_USERNAMES`. Full suite + CI (full collection) unaffected. | 01-02 Auth shim (exposed pre-existing fixture assumption) | Harden the fixture to not depend on `core.auth` being cached; low priority (full-suite/CI green) |

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-07-01 18:36 UTC
Stopped at: **Phase 1 COMPLETE** — 01-01 Documents (PR #3, `b049650`) and 01-02 Auth (PR #4, `dcde7b1`) both shipped; local dev synced; PAUL reconciled to 5/9 domains. Auth left a deferred follow-up (test_auth_regressions subset fragility — see Deferred Issues).
Next action: Begin Phase 2 (medium-risk). GROUND 02-01 (Calendar/Contacts) — re-derive live line counts + importer/patch-target + source-path-introspection audit; settle the OPEN CALL: co-locate calendar+contacts in one routes/calendar/ package vs two separate packages.
Resume file: .paul/phases/ (Phase 2 dir + 02-01-PLAN.md to be created after grounding)

---
*STATE.md — Updated after every significant action*
