# Project State

## Project Reference

See: .paul/PROJECT.md (updated 2026-07-01)

**Core value:** Contributors can navigate and safely change the backend because domain
logic lives in discoverable, right-sized modules — zero behavior change, no broken imports.
**Current focus:** v0.1 Backend Module Boundaries (Slice 2, multi-file domains) — **Phase 2 COMPLETE**; Phase 3 (Chat/Agent, last) not started.

## Current Position

Milestone: v0.1 Backend Module Boundaries
Phase: 3 of 3 — Chat/Agent (highest-risk, last) — **NOT STARTED** (Phases 1 & 2 COMPLETE)
Plan: Phase 2 CLOSED — 02-01 (Calendar/Contacts, PR #5), 02-02 (Model/LLM, PR #7 `bd32ccb`), 02-03 (Cookbook, PR #8 `dbc7be5`) all SHIPPED + UNIFIED. Phase 3 plan 03-01 not yet authored.
Status: 02-03 loop CLOSED (PLAN✓ APPLY✓ UNIFY✓ SHIPPED✓). Phase 2→3 transition executed. Co-located `routes/cookbook/` package + 3 shims, byte-identical; full suite 4292 passed / 0 new failures; internal audit + feature QA + Codex diff review all PASS/0 findings. Only remaining v0.1 domain: Chat/Agent (Phase 3, 03-01) — shape is an OPEN CALL (see ROADMAP §Phase 3): all five of chat/shell/codex/skills into `routes/chat/`, or `routes/chat/` = chat_routes+chat_helpers only with shell/codex/skills left flat (recommendation leans the latter).
Last activity: 2026-07-04 — 02-03 Cookbook SHIPPED (PR #8 merged as `dbc7be5`); Phase 2 UNIFIED + transitioned to Phase 3. Reconciled stale ROADMAP/PROJECT (Phase-1 & Phase-2 transitions had never refreshed them).

Progress:
- Milestone: [█████████░] 89% by domain (8 of 9 shipped; only Chat/Agent remains)
- Phase 1: [██████████] 100% (2 of 2 plans complete — document, auth)
- Phase 2: [██████████] 100% COMPLETE (3 of 3 shipped: 02-01 + 02-02 + 02-03)
- Phase 3: [░░░░░░░░░░] 0% (0 of 1 — not started)

## Loop Position

Current loop state:
```
PLAN ──▶ APPLY ──▶ UNIFY ──▶ SHIPPED
  ✓        ✓         ✓         ✓   [02-03 loop CLOSED. Phase 2 COMPLETE (02-01 PR #5, 02-02 PR #7, 02-03 PR #8 dbc7be5). Next: PLAN 03-01 Chat/Agent.]
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

Last session: 2026-07-04 — 02-03 Cookbook SHIPPED (PR #8 `dbc7be5`); Phase 2 UNIFIED + transitioned to Phase 3.
Stopped at: **Phase 2 COMPLETE, transitioned to Phase 3 (not started)**. All three Phase-2 domains shipped: 02-01 Calendar/Contacts (PR #5), 02-02 Model/LLM (PR #7 `bd32ccb`), 02-03 Cookbook (PR #8 `dbc7be5`). 02-03 = co-located `routes/cookbook/` (`routes.py` 3,501 + `helpers.py` 1,365 + `output.py` 75 + docstring-only `__init__`) behind 3 `sys.modules` shims, byte-identical; 9 test literals repointed + guard test; full suite 4292 passed / 0 new failures; audit + QA + Codex diff review all PASS/0. This UNIFY also reconciled ROADMAP.md + PROJECT.md, which had drifted (Phase-1 & Phase-2 transitions never refreshed them — ROADMAP still read "0 of 3 phases complete").
Next action: **PLAN 03-01 Chat/Agent** (last v0.1 domain, Phase 3, HIGH-risk) — but FIRST settle the OPEN CALL (ROADMAP §Phase 3): (a) all five chat/shell/codex/skills → `routes/chat/`, vs (b) `routes/chat/` = chat_routes+chat_helpers only, shell/codex/skills stay flat (recommendation leans b — don't over-bundle unrelated surfaces). Suggested pre-plan: `/paul:ground` or `/paul:discuss` for the chat/agent shape before `/paul:plan`. After 03-01 ships → v0.1 milestone complete → `/paul:complete-milestone`.
Bookkeeping note: this Phase-2-close UNIFY landed on branch `chore/paul-02-03-unify-phase2-close` → PR to `dev` (no direct commits to `dev`, per project rule + global no-commit-to-main rule).
OUTSTANDING (harness, NOT this repo): enforce "always second-opinion the PLAN before APPLY" as a HARD gate in the PAUL `/paul:apply` workflow. Per the session-directory rule this is harness work — do it from a `~/.claude`-rooted session, not odysseus. (Apply-gate fence already deployed + settled per docs/handoff/2026-07-04-session-close-02-02-shipped-and-harness-settled.md.)
Resume file: .paul/ROADMAP.md

---
*STATE.md — Updated after every significant action*
