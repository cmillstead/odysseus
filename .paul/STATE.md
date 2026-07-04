# Project State

## Project Reference

See: .paul/PROJECT.md (updated 2026-07-01)

**Core value:** Contributors can navigate and safely change the backend because domain
logic lives in discoverable, right-sized modules — zero behavior change, no broken imports.
**Current focus:** v0.1 Backend Module Boundaries (Slice 2, multi-file domains) — Phase 2 in progress; 02-01 shipped.

## Current Position

Milestone: v0.1 Backend Module Boundaries
Phase: 2 of 3 — Medium-risk domains — **IN PROGRESS** (02-01 shipped, 02-02 UNIFIED)
Plan: 02-01 (Calendar/Contacts, PR #5) SHIPPED. 02-02 (Model/LLM) UNIFIED + Codex-approved — PR #7 OPEN, merge held by user.
Status: 02-02 loop CLOSED (PLAN✓ APPLY✓ UNIFY✓); SUMMARY reconciled against all 6 ACs, full suite green at baseline parity, Codex diff review APPROVED (0 findings). PR #7 to `dev` is CLEAN/MERGEABLE — user chose to hold the merge. Next: merge PR #7, then PLAN 02-03 (Cookbook).
Last activity: 2026-07-04 — 02-02 UNIFY complete; SUMMARY confirmed complete (was written during APPLY as c1c7dbe); paul.json synced to Phase 2. Applied under logged override (gate had no recorded artifact for the pre-recorder 3-round plan review).

Progress:
- Milestone: [███████░░░] 67% by domain (6 of 9 merged; 02-02 applied, not yet merged)
- Phase 1: [██████████] 100% (2 of 2 plans complete)
- Phase 2: [███████░░░] 67% (2 of 3 applied: 02-01 shipped, 02-02 applied/PR-pending)

## Loop Position

Current loop state:
```
PLAN ──▶ APPLY ──▶ UNIFY ──▶ SHIPPED
  ✓        ✓         ✓         ·   [02-02 loop CLOSED. PR #7 OPEN (CLEAN) — merge held by user. 02-01 shipped (PR #5).]
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

Last session: 2026-07-04 — 02-02 Model/LLM UNIFIED (loop closed).
Stopped at: **Phase 2 domain 2/3 UNIFIED** — 02-02 Model/LLM loop CLOSED (PLAN✓ APPLY✓ UNIFY✓). Co-located `routes/model/` package + 3 shims; shim-reload gotcha fixed across shared helper + 4 sites; full suite 4284 passed / 0 new failures; Codex diff review APPROVED (0 findings). SUMMARY at `.paul/phases/02-medium-risk-domains/02-02-SUMMARY.md`. paul.json synced to Phase 2. PR #7 (`refactor/routes-model-domain` → `dev`) is OPEN + CLEAN/MERGEABLE — user chose to hold the merge this session.
Next action: (1) merge PR #7 to `dev` when ready (CLEAN, Codex-approved) → completes 02-02 SHIP; (2) then PLAN 02-03 Cookbook (last Phase-2 domain — no PLAN authored yet) via `/paul:plan`. Phase 2 → transition fires only after 02-03 ships.
OUTSTANDING (harness, NOT this repo): enforce "always second-opinion the PLAN before APPLY" as a HARD gate in the PAUL `/paul:apply` workflow. Per the session-directory rule this is harness work — do it from a `~/.claude`-rooted session, not odysseus. (Apply-gate fence already deployed + settled per docs/handoff/2026-07-04-session-close-02-02-shipped-and-harness-settled.md.)
Resume file: .paul/phases/02-medium-risk-domains/02-02-SUMMARY.md

---
*STATE.md — Updated after every significant action*
