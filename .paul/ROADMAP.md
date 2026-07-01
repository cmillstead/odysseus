# Roadmap: Odysseus Backend Architecture Refactor

## Overview

Behavior-preserving decomposition of the Odysseus backend into right-sized, discoverable
modules. v0.1 completes **Slice 2** — packaging the flat `routes/` directory by domain —
for the genuine **multi-file domains** only, each delivered as an atomic, shim-backed,
one-domain-per-PR change validated against the test baseline. Single-file routes stay flat
(already "one domain = one file"). Higher-risk slices (agent_loop, `src/` layering,
database) and `ai_interaction.py` cleanup are later milestones.

> Domain boundaries follow the authoritative Route Ownership Map in
> `specs/architecture-runtime-inventory.md` §4 (grounded 2026-07-01).

## Current Milestone

**v0.1 Backend Module Boundaries** (v0.1.0) — Slice 2, multi-file domains
Status: In progress
Phases: 0 of 3 complete · Domains: 3 of 9 done (email, gallery, research)

## Phases

| Phase | Name | Plans | Status | Completed |
|-------|------|-------|--------|-----------|
| 1 | Low-risk domains (warm the pattern) | 2 | Planned (ready to apply) | - |
| 2 | Medium-risk domains | 3 | Not started | - |
| 3 | Chat/Agent (highest-risk, last) | 1 | Not started | - |

## Phase Details

### Phase 1: Low-risk domains

**Goal:** Package the two LOW-complexity multi-file domains to re-warm the shim pattern
after email, before touching the bigger ones. One domain per plan / per PR.
**Depends on:** Nothing (pattern proven on email/gallery/research).
**Research:** Unlikely.

**Plans:**
- [ ] 01-01: `routes/document/` — document_routes.py + document_helpers.py + shim (LOW, 1,954 ln)
- [ ] 01-02: `routes/auth/` — auth_routes.py + api_token_routes.py + device_flow.py + shim (LOW, 1,171 ln)

### Phase 2: Medium-risk domains

**Goal:** Package the three MEDIUM-complexity domains. Note two of these are *themed*
groupings of standalone files (no shared `_helpers`) — co-locating related routes rather
than splitting shared code; confirm that's the desired shape at plan time.
**Depends on:** Phase 1.
**Research:** Unlikely.

**Plans:**
- [ ] 02-01: `routes/calendar/` — calendar_routes.py + contacts_routes.py + shim (MEDIUM, 2,336 ln) — *themed grouping; confirm calendar+contacts belong together vs two packages*
- [ ] 02-02: `routes/model/` — model_routes.py + assistant_routes.py + copilot_routes.py + shim (MEDIUM, 2,764 ln) — *themed grouping of standalone files*
- [ ] 02-03: `routes/cookbook/` — cookbook_routes.py (188 KB) + cookbook_helpers.py + cookbook_output.py + shim (MEDIUM, 4,110 ln)

### Phase 3: Chat/Agent (highest-risk, last)

**Goal:** Package the HIGH-complexity core interaction surface. §4 buckets this as
chat + shell + codex + skills (6,365 ln), but `shell_routes`/`codex_routes`/`skills_routes`
are **standalone files with no shared helpers** — only chat_routes + chat_helpers form a
true shared-code cluster.
**OPEN CALL (settle at plan time):** either (a) move all five into `routes/chat/` as a themed
package, or (b) make `routes/chat/` = chat_routes + chat_helpers only and leave shell/codex/
skills flat (they're singletons). Recommendation leans (b) — don't over-bundle unrelated
surfaces under "chat".
**Depends on:** Phase 2 (pattern fully warm; biggest/most-coupled domain last).
**Research:** Unlikely.

**Plans:**
- [ ] 03-01: `routes/chat/` package + shim (scope decided by the OPEN CALL above)

## Explicitly Out of Scope for v0.1 (grounded 2026-07-01)

- **`ai_interaction.py` split** — assigned to NO slice in the fork spec (§6); the #3629
  tool→registry migration it references is already largely done (`src/agent_tools/`).
  It's a 1,846-line shared-infra module; any cleanup is a *later* milestone, not "Slice 1".
- **Slice 1 is complete** — `tool_implementations.py` → `src/tools/` shipped. (Note: the
  tree has BOTH `src/tools/` and `src/agent_tools/` — two distinct tool packages.)
- **Single-file route domains stay flat** — task, session, memory, mcp, notes, run,
  learning, and the 23-file "Other" bucket (§4). Packaging one file into `routes/x/` adds
  indirection without structural gain.
- **Singleton grouping** — if ever wanted, a separate v0.1.x pass (thematic bundling of
  the "Other" files), not this milestone.

## Later Milestones (not started)

| Version | Focus | Notes |
|---------|-------|-------|
| v0.2 | Slice 3 — `agent_loop.py` → `src/agent/` | MEDIUM-HIGH risk (2,961 lines) |
| v0.2.x | `ai_interaction.py` decomposition | Shared-infra module; optional cleanup |
| v0.3 | Slice 4 — flat `src/` → layered packages | After routes + tools stable |
| v0.4 | Slice 6 — `core/database.py` split | HIGH risk (102 importers); last |
| v0.5+ | Slices 7–8 — frontend CSS/JS | Separate timeline (#2617) |

---
*Roadmap created: 2026-07-01 · Grounded against codebase + spec §4: 2026-07-01*
