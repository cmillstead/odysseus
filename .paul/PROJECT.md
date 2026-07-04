# Odysseus Backend Architecture Refactor

## What This Is

A behavior-preserving refactor of the Odysseus Python backend to establish clear
runtime module boundaries. It splits oversized flat modules (`tool_implementations.py`,
the flat `routes/` directory, `agent_loop.py`, `core/database.py`) into cohesive
packages, using `sys.modules`/`__init__.py` compatibility shims so every existing
import path and `mock.patch(...)` target keeps working unchanged. No runtime behavior
changes — pure reorganization, validated against the test-suite baseline on each slice.

The work is scoped by the Phase-0 inventory in `specs/architecture-runtime-inventory.md`.

## Core Value

Contributors can navigate and safely change the backend because domain logic lives in
discoverable, right-sized modules instead of multi-thousand-line flat files — with zero
behavior change and no broken import paths along the way.

## Current State

| Attribute | Value |
|-----------|-------|
| Type | Application (Python / FastAPI backend) |
| Version | 0.0.0 |
| Status | In progress — Phases 1 & 2 complete, Phase 3 (Chat/Agent) remaining |
| Last Updated | 2026-07-04 |

## Requirements

### Core Features (refactor slices, from `specs/architecture-runtime-inventory.md` §6)

- Slice 1 — `tool_implementations.py` → `src/tools/` package (+ `ai_interaction.py` split)
- Slice 2 — flat `routes/` → per-domain packages, **one domain per PR**, shim-backed
- Slice 3 — `agent_loop.py` → `src/agent/` submodules
- Slice 4 — flat `src/` → layered `src/{pkg,domain,infra,api}/`
- Slice 6 — `core/database.py` → `src/infra/database/models/` (HIGH risk, **last**)
- Slices 7–8 — frontend CSS/JS modularization (separate timeline)

### Validated (Shipped)

- [x] Slice 1 — `tool_implementations.py` → `src/tools/` (11 files) — **complete** on fork `dev`
      (note: tree has BOTH `src/tools/` and `src/agent_tools/` — two distinct tool packages)
- [x] Slice 2 — `routes/gallery/` domain package (shim pattern) — on fork `dev`
- [x] Slice 2 — `routes/research/` domain package — on fork `dev`
- [x] Slice 2 — `routes/email/` domain package — merged 2026-07-01 (fork PR #2)
- [x] Slice 2 — `routes/document/` domain package — merged 2026-07-01 (fork PR #3, merge `b049650`)
- [x] Slice 2 — `routes/auth/` domain package — merged 2026-07-01 (fork PR #4, merge `dcde7b1`) — **Phase 1 complete**
- [x] Slice 2 — `routes/calendar/` + `routes/contacts/` domain packages (two separate) — merged 2026-07-01 (fork PR #5, merge `5907c96`) — **first Phase 2 domain**
- [x] Slice 2 — `routes/model/` domain package (model + assistant + copilot, co-located) — merged 2026-07-04 (fork PR #7, merge `bd32ccb`)
- [x] Slice 2 — `routes/cookbook/` domain package (routes + helpers + output, co-located, byte-identical) — merged 2026-07-04 (fork PR #8, merge `dbc7be5`) — **Phase 2 complete**

### Active (In Progress)

- [ ] v0.1 milestone: Slice 2 — package the **last** remaining multi-file route domain (Chat/Agent, Phase 3)

### Planned (Next) — grounded 2026-07-01, spec §4 boundaries

- [ ] Chat/Agent (chat_routes + chat_helpers; shell/codex/skills shape TBD) — HIGH ← **next (03-01), last v0.1 domain**

### Out of Scope (for v0.1)

- **`ai_interaction.py` split** — assigned to no slice in the fork spec; #3629 migration
  already largely done (`src/agent_tools/`). Later milestone (v0.2.x), NOT "Slice 1".
- **Single-file route domains** stay flat — task, session, memory, mcp, notes, run,
  learning, and the 23-file "Other" bucket (§4). Grouping them is an optional later pass.
- Slice 3 (`agent_loop.py`) — later milestone
- Slice 4 (`src/` layering) — must follow routes + tools stabilizing
- Slice 6 (`core/database.py`) — HIGH risk (102 importers); deliberately last
- Slices 7–8 (frontend) — separate timeline (#2617)
- No behavior changes, no packaging/tooling migration, no framework migration

## Constraints

### Technical Constraints

- **Behavior-preserving only** — no logic changes mixed into file moves.
- **Compatibility shims mandatory** — old import paths and `mock.patch("routes.x.Y")`
  targets must resolve to the *same* module object (via `sys.modules[__name__] = _real`).
- **One domain/slice per PR** — never mix reorganizations (maintainer guidance #4082/#4071).
- **Validation gate per slice** — `python -m compileall`, `node --check` (if FE touched),
  and full `pytest` must match the baseline pass rate before opening each PR.
- **CI is dormant** — `cmillstead/odysseus` is a fork; workflows are unregistered until
  enabled in the Actions tab. Verification is local on every commit.
- **PEP-420 namespace packages** — `src`/`routes`/`core` have no `__init__.py` in places;
  worktree test runs need explicit `PYTHONPATH` + `python -P` to avoid module shadowing.

### Business Constraints

- Fork-local delivery: work lands on `cmillstead/odysseus` `dev`, not upstream.

## Key Decisions

| Decision | Rationale | Date | Status |
|----------|-----------|------|--------|
| Fork-local is the source of truth | Avoid naming churn (`src/tools/` stays, not `src/agent_tools`); "done" = clean on fork `dev`. Upstream issues (#3629/#3266/#2617) are reference only. | 2026-07-01 | Active |
| v0.1 = Slice 2 multi-file domains only | Grounding (2026-07-01) showed Slice 1 already complete under fork-local truth and `ai_interaction.py` assigned to no slice; singletons add indirection without gain. Defer agent_loop / src-layering / database. | 2026-07-01 | Active |
| Domain boundaries follow spec §4 | The authoritative Route Ownership Map groups differently than the first-draft roadmap (e.g. Calendar/Contacts = one domain; Chat/Agent bundles chat+shell+codex+skills). | 2026-07-01 | Active |
| `sys.modules` alias shim pattern | Preserves `mock.patch` targets and every import path across the move (proven on gallery/research/email). | 2026-06 | Active |
| One domain per PR | Route modules carry helper imports, registration assumptions, and test import paths — atomic per-domain PRs keep review + rollback clean. | 2026-06 | Active |
| Co-locate themed groupings (Model, Cookbook) into one package; split zero-shared-code groupings (Calendar/Contacts) | Model = themed standalone files with an intra-domain edge; Cookbook = routes+helpers+output with a real internal DAG → one `routes/{model,cookbook}/` package each. Calendar/Contacts share no code → two packages. Shape decided per-domain at plan time. | 2026-07-04 | Active |

## Success Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Test-suite parity per slice | 0 new failures vs baseline | baseline: 3 pre-existing failures | On track |
| `python -m compileall` | clean on every PR | clean | On track |
| Multi-file route domains packaged (v0.1) | 9 / 9 | 8 / 9 (email, gallery, research, document, auth, calendar+contacts, model, cookbook) — only Chat/Agent left | In progress |
| Slice 1 (tool_implementations → src/tools/) | complete | complete | Achieved |

## Tech Stack / Tools

| Layer | Technology | Notes |
|-------|------------|-------|
| Language | Python 3 | Backend |
| Web framework | FastAPI | Routers registered in `app.py` |
| Persistence | SQLite (SQLAlchemy) | `core/database.py` (Slice 6 target) |
| Tests | pytest | Real implementations, temp DBs — no mocks per project rule |
| Review gate | Codex CLI (`/second-opinion`) | Cross-model review per slice |

---
*Created: 2026-07-01 · Last updated: 2026-07-04 after Phase 2 (Medium-risk domains) complete*
