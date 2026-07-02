# Project State

## Project Reference

See: .paul/PROJECT.md (updated 2026-07-01)

**Core value:** Contributors can navigate and safely change the backend because domain
logic lives in discoverable, right-sized modules — zero behavior change, no broken imports.
**Current focus:** v0.1 Backend Module Boundaries (Slice 2, multi-file domains) — Phase 2 in progress; 02-01 shipped.

## Current Position

Milestone: v0.1 Backend Module Boundaries
Phase: 2 of 3 — Medium-risk domains — **IN PROGRESS** (02-01 Calendar/Contacts COMPLETE)
Plan: 02-01 (Calendar/Contacts, PR #5) SHIPPED. 02-02 (Model/LLM) GROUNDED + PLANNED — ready to APPLY.
Status: 02-02 pre-planning gate done (GROUND + PLAN); shape RESOLVED = (A) one co-located `routes/model/` package → APPLY next
Last activity: 2026-07-02 — 02-02 grounded (shim-reload gotcha lands in shared helper `tests/helpers/import_state.py`; model is a hub) + planned; on branch `refactor/routes-model-domain`

Progress:
- Milestone: [███████░░░] 67% by domain (6 of 9 merged: email, gallery, research, document, auth, calendar+contacts)
- Phase 1: [██████████] 100% (2 of 2 plans complete)
- Phase 2: [███░░░░░░░] 33% (1 of 3 plans complete: 02-01)

## Loop Position

Current loop state:
```
PLAN ──▶ APPLY ──▶ UNIFY ──▶ SHIPPED
  ✓        ·         ·         ·   [02-02 PLANNED (shape A) — APPLY next. 02-01 shipped (PR #5).]
```

## Accumulated Context

### Decisions

| Decision | Impact |
|----------|--------|
| Fork-local is source of truth | `src/tools/` naming stays; upstream issues reference-only |
| v0.1 = finish Slice 1 + all Slice 2 | Defers agent_loop / src-layering / database to later milestones |
| `sys.modules` alias shim pattern | Preserves import paths + `mock.patch` targets across every move |
| One domain per PR | Atomic, reviewable, behavior-preserving slices |
| 2026-07-01: 02-01 Calendar/Contacts = TWO SEPARATE packages | Files share zero code (no mutual import, no shared helper, distinct CalDAV/CardDAV stacks) → `routes/calendar/` + `routes/contacts/`, not co-located |

### Deferred Issues

| Issue | Origin | Revisit |
|-------|--------|---------|
| `ai_interaction.py` decomposition (1,846 ln shared infra) | Grounding | v0.2.x milestone (NOT Slice 1) |
| Chat/Agent shape — bundle shell/codex/skills into routes/chat/ or leave flat | Grounding | Plan-time for 03-01 |
| Themed grouping Model+Assistant+Copilot — co-locate vs separate (Calendar+Contacts RESOLVED 2026-07-01: two separate packages, shipped 02-01) | Grounding | Plan-time for 02-02 |
| Shim-reload gotcha: tests that "swap a dependency + `delitem`/reimport the target" break under alias shims — reimporting the old flat path only re-runs the shim; must delete + import the canonical dotted module name to force re-execution (`from pkg import mod` won't reload if the package object still holds the attr). Fixed in `test_calendar_owner_scope.py` (02-01). | 02-01 shim | Watch at plan/qualify time for 02-02 (Model) and 02-03 (Cookbook) |
| Singleton "Other" bucket (23 files) grouping | Grounding | Optional v0.1.x pass |
| `implementation-spec-capability-gaps.md` (WS-0..25) | Feature roadmap, separate | After backend boundaries milestone |
| `test_auth_regressions.py` subset-run fragility — its `_ensure_stub`/`_auth_regressions_stubs` fixture assumes `core.auth` is pre-loaded; the auth shim (01-02) stopped pop-and-reimport from re-establishing it, so running the auth files as a NARROW subset now ImportErrors on `RESERVED_USERNAMES`. Full suite + CI (full collection) unaffected. | 01-02 Auth shim (exposed pre-existing fixture assumption) | Harden the fixture to not depend on `core.auth` being cached; low priority (full-suite/CI green) |

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-07-01 — 02-01 Calendar/Contacts shipped.
Stopped at: **Phase 2 domain 1/3 COMPLETE** — 02-01 Calendar/Contacts (PR #5, merge `5907c96`) shipped; two separate packages behind shims; full suite 4273 passed / 0 new failures; Codex clean. A shim-induced regression in `test_calendar_owner_scope.py` was found and fixed (see Deferred Issues → shim-reload gotcha for the carry-forward). SUMMARY at `.paul/phases/02-medium-risk-domains/02-01-SUMMARY.md`.
Next action: APPLY 02-02 — plan is Codex-reviewed (**3 rounds → PASS**, commit `22f87d5`). Dispatch the implementer
for `.paul/phases/02-medium-risk-domains/02-02-PLAN.md` (Tasks 1-4), then orchestrator runs the full-suite Qualify
(Task 5) → Codex diff review → PR to dev. On branch `refactor/routes-model-domain`. Headline risk: the 5-site
shim-reload fix (Task 3). Full handoff: `docs/handoff/2026-07-02-paul-model-domain.md`.
OUTSTANDING (user's strong ask): enforce "always second-opinion the PLAN before APPLY" as a HARD gate in the PAUL
`/paul:apply` workflow via `/harness-engineer` (memory can't enforce it). User was choosing APPLY-first vs
enforcement-first at the clear.
Resume file: docs/handoff/2026-07-02-paul-model-domain.md → .paul/phases/02-medium-risk-domains/02-02-PLAN.md

---
*STATE.md — Updated after every significant action*
