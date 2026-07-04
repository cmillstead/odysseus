# Project State

## Project Reference

See: .paul/PROJECT.md (updated 2026-07-01)

**Core value:** Contributors can navigate and safely change the backend because domain
logic lives in discoverable, right-sized modules — zero behavior change, no broken imports.
**Current focus:** v0.1 Backend Module Boundaries (Slice 2, multi-file domains) — **Phase 3 Chat/Agent applied on branch `codex/phase3-chat-agent`**, pending review/merge.

## Current Position

Milestone: v0.1 Backend Module Boundaries
Phase: 3 of 3 — Chat/Agent (highest-risk, last) — **APPLIED ON BRANCH** (Phases 1 & 2 COMPLETE)
Plan: 03-01 Chat/Agent applied on `codex/phase3-chat-agent`: `routes/chat/` = chat routes + helpers only; shell/codex/skills stay flat. Branch review/merge remains.
Status: 03-01 loop APPLY in progress/verification: package + shims + guard test added; PAUL docs updated branch-locally. UNIFY/SHIPPED are pending branch review/merge to `dev`.
Last activity: 2026-07-04 — 03-01 Chat/Agent package applied in branch; root `AGENTS.md` added because repo had no AGENTS.md.

Progress:
- Milestone: [██████████] 100% by domain in branch (9 of 9 applied; merge pending)
- Phase 1: [██████████] 100% (2 of 2 plans complete — document, auth)
- Phase 2: [██████████] 100% COMPLETE (3 of 3 shipped: 02-01 + 02-02 + 02-03)
- Phase 3: [██████████] 100% applied in branch (1 of 1 — merge pending)

## Loop Position

Current loop state:
```
PLAN ──▶ APPLY ──▶ UNIFY ──▶ SHIPPED
  ✓        ◐         ·         ·   [03-01 Chat/Agent applied on branch; verification/commit/PR merge pending.]
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
| 2026-07-04: 03-01 Chat/Agent = narrow `routes/chat/` package | `chat_routes.py` + `chat_helpers.py` move together; `shell_routes.py`, `codex_routes.py`, and `skills_routes.py` stay flat |

### Deferred Issues

| Issue | Origin | Revisit |
|-------|--------|---------|
| `ai_interaction.py` decomposition (1,846 ln shared infra) | Grounding | v0.2.x milestone (NOT Slice 1) |
| Branch review/merge for 03-01 Chat/Agent | Apply branch | before v0.1 milestone close |
| Themed grouping Model+Assistant+Copilot — co-locate vs separate (Calendar+Contacts RESOLVED 2026-07-01: two separate packages, shipped 02-01) | Grounding | Plan-time for 02-02 |
| Shim-reload gotcha: tests that "swap a dependency + `delitem`/reimport the target" break under alias shims — reimporting the old flat path only re-runs the shim; must delete + import the canonical dotted module name to force re-execution (`from pkg import mod` won't reload if the package object still holds the attr). Fixed in `test_calendar_owner_scope.py` (02-01). | 02-01 shim | Watch at plan/qualify time for 02-02 (Model) and 02-03 (Cookbook) |
| Singleton "Other" bucket (23 files) grouping | Grounding | Optional v0.1.x pass |
| `implementation-spec-capability-gaps.md` (WS-0..25) | Feature roadmap, separate | After backend boundaries milestone |
| `test_auth_regressions.py` subset-run fragility — its `_ensure_stub`/`_auth_regressions_stubs` fixture assumes `core.auth` is pre-loaded; the auth shim (01-02) stopped pop-and-reimport from re-establishing it, so running the auth files as a NARROW subset now ImportErrors on `RESERVED_USERNAMES`. Full suite + CI (full collection) unaffected. | 01-02 Auth shim (exposed pre-existing fixture assumption) | Harden the fixture to not depend on `core.auth` being cached; low priority (full-suite/CI green) |

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-07-04 — 03-01 Chat/Agent APPLY started and package move completed on branch `codex/phase3-chat-agent`.
Stopped at: **03-01 applied in branch, verification/commit/merge pending**. Shape resolved to narrow `routes/chat/` package with `routes.py` + `helpers.py`; `shell_routes.py`, `codex_routes.py`, and `skills_routes.py` stay flat. Added `AGENTS.md`, two chat shims, docstring-only `routes/chat/__init__.py`, and `tests/test_chat_package_shim.py`; repointed source-inspection tests to canonical files.
Next action: finish verification, commit branch, then open/merge PR to `dev`; after merge, complete v0.1 milestone.
Bookkeeping note: this Phase-2-close UNIFY landed on branch `chore/paul-02-03-unify-phase2-close` → PR to `dev` (no direct commits to `dev`, per project rule + global no-commit-to-main rule).
OUTSTANDING (harness, NOT this repo): enforce "always second-opinion the PLAN before APPLY" as a HARD gate in the PAUL `/paul:apply` workflow. Per the session-directory rule this is harness work — do it from a `~/.claude`-rooted session, not odysseus. (Apply-gate fence already deployed + settled per docs/handoff/2026-07-04-session-close-02-02-shipped-and-harness-settled.md.)
Resume file: .paul/ROADMAP.md

---
*STATE.md — Updated after every significant action*
