# Project State

## Project Reference

See: .paul/PROJECT.md (updated 2026-07-01)

**Core value:** Contributors can navigate and safely change the backend because domain
logic lives in discoverable, right-sized modules — zero behavior change, no broken imports.
**Current focus:** v0.1 Backend Module Boundaries (Slice 2, multi-file domains) — Phase 2 in progress; 02-01 + 02-02 shipped, 02-03 applied.

## Current Position

Milestone: v0.1 Backend Module Boundaries
Phase: 2 of 3 — Medium-risk domains — **IN PROGRESS** (02-01 + 02-02 SHIPPED, 02-03 APPLIED)
Plan: 02-01 (Calendar/Contacts, PR #5) SHIPPED. 02-02 (Model/LLM, PR #7) SHIPPED — merged to `dev` as `bd32ccb`. 02-03 (Cookbook) APPLIED + Codex-approved — PR to `dev` pending.
Status: 02-03 loop PLAN✓ APPLY✓ (UNIFY next). Co-located `routes/cookbook/` package + 3 shims, byte-identical move; full suite 4292 passed / 0 new failures; internal audit (spec+simplify+harden) + feature QA all PASS/0 findings; Codex diff review PASS (0 defects, live-probed identity + mock.patch visibility). No import_state.py/reload-site changes (shim-reload gotcha absent). SUMMARY at 02-03-SUMMARY.md. Next: open PR to `dev`, then UNIFY 02-03 → Phase 2 transition fires after 02-03 ships.
Last activity: 2026-07-04 — 02-02 SHIPPED (PR #7 merged as bd32ccb; supersedes prior "merge held" note). 02-03 Cookbook APPLIED via /coding-team (implementer Tasks 1–4, byte-identical, 0 new failures) — Codex-PASS on both plan (3 rounds) and diff.

Progress:
- Milestone: [████████░░] 78% by domain (7 of 9 merged; 02-03 applied, PR pending)
- Phase 1: [██████████] 100% (2 of 2 plans complete)
- Phase 2: [██████████] 100% applied (3 of 3: 02-01 + 02-02 shipped, 02-03 applied/PR-pending)

## Loop Position

Current loop state:
```
PLAN ──▶ APPLY ──▶ UNIFY ──▶ SHIPPED
  ✓        ✓         ·         ·   [02-03 APPLY complete — PR to `dev` pending, UNIFY next. 02-01 (PR #5) + 02-02 (PR #7, bd32ccb) SHIPPED.]
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

Last session: 2026-07-04 — 02-03 Cookbook APPLIED via /coding-team (PR to `dev` pending).
Stopped at: **Phase 2 domain 3/3 APPLIED** — 02-03 Cookbook loop PLAN✓ APPLY✓ (UNIFY next). Co-located `routes/cookbook/` package (`routes.py` 3,501 + `helpers.py` 1,365 + `output.py` 75 + docstring-only `__init__`) behind 3 `sys.modules` shims; byte-identical move (empty content diffs), no shim-reload gotcha (absent for cookbook). 9 source-path test literals repointed across 4 files (both slash- and segment-joined forms) + guard test `test_cookbook_package_shim.py`. Full suite 4292 passed / 0 new failures; internal audit + feature QA + Codex diff review all PASS/0 findings. SUMMARY at `.paul/phases/02-medium-risk-domains/02-03-SUMMARY.md`. Commits `d604b36` (move) + `9d4fcb0` (guard test) on `refactor/routes-cookbook-domain`.
Also this session: reconciled stale STATE — 02-02 PR #7 is MERGED (`bd32ccb`), not "held"; marked 02-02 SHIPPED.
Next action: (1) open PR (`refactor/routes-cookbook-domain` → `dev`) — includes this SUMMARY + STATE bump; (2) merge it → completes 02-03 SHIP; (3) UNIFY 02-03 (sync paul.json + final STATE). Phase 2 → 3 transition fires only after 02-03 ships (last Phase-2 domain). Then MEDIUM domains done; Slice 2 domain 9/9 (singleton "Other" bucket) + Phase 3 remain.
OUTSTANDING (harness, NOT this repo): enforce "always second-opinion the PLAN before APPLY" as a HARD gate in the PAUL `/paul:apply` workflow. Per the session-directory rule this is harness work — do it from a `~/.claude`-rooted session, not odysseus. (Apply-gate fence already deployed + settled per docs/handoff/2026-07-04-session-close-02-02-shipped-and-harness-settled.md.)
Resume file: .paul/phases/02-medium-risk-domains/02-03-SUMMARY.md

---
*STATE.md — Updated after every significant action*
