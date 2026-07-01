# Grounding Report — v0.1 milestone (Slice 2 route domains)

_Grounded 2026-07-01 against fork `dev` + `specs/architecture-runtime-inventory.md` §4/§5/§6._
_This merges the /paul:assumptions surfacing with the /paul:ground verification._

## Assumptions tested → verdicts

| # | Roadmap assumption | Verdict | Evidence |
|---|--------------------|---------|----------|
| 1 | Phase 1 = "finish Slice 1" by splitting `ai_interaction.py` | ❌ **WRONG** | Spec §6 assigns `ai_interaction.py` to **no slice**; it appears only in the §2.1 size inventory (1,846 ln). The "split it" idea came from *upstream* #3629, set aside by the fork-local decision. Its own docstring shows #3629's migration already moved the tool funcs to `src/agent_tools/`. → **Slice 1 is done; Phase 1 dropped.** |
| 2 | One `src/tools/` package | ❌ **WRONG** | Tree has BOTH `src/tools/` and `src/agent_tools/` (distinct tool packages). |
| 3 | ~15 route domains, grouped chat/model/session · cookbook/document/notes/calendar/contacts · skills/task/shell/codex/mcp/run/learning/memory | ❌ **WRONG grouping** | Spec §4: Chat/Agent = chat+shell+codex+skills (ONE domain); Model = model+assistant+copilot; Calendar/Contacts = ONE domain; most others are single-file; a 23-file "Other" bucket. |
| 4 | run/learning/memory are a natural cluster wired by PR #1 | ⚠️ **Partial** | Files exist but `run`/`learning` postdate the spec (not in §4); only `memory` is in §4. All single-file → out of v0.1 scope. |
| 5 | Singletons should be packaged | ❓ → **Decided NO** | Slice 2 rationale is grouping multi-file domains. Single-file packaging adds indirection without gain. |
| 6 | email/gallery/research done; shim pattern proven; cookbook & documents are real clusters | ✅ **Held** | Confirmed on tree. |

## Decisions taken (from grounding)

1. **Drop the ai_interaction.py phase.** v0.1 = Slice 2 only. `ai_interaction.py` → later milestone (v0.2.x), not "Slice 1".
2. **Package multi-file clusters only.** Single-file routes stay flat.
3. **Domain boundaries follow spec §4**, not the invented grouping.

## Grounded v0.1 domain set (remaining, excluding done email/gallery/research)

| Domain | Files | Lines | Risk | Phase |
|--------|-------|-------|------|-------|
| Documents | document_routes, document_helpers | 1,954 | LOW | 1 |
| Auth | auth_routes, api_token_routes, device_flow | 1,171 | LOW | 1 |
| Calendar/Contacts | calendar_routes, contacts_routes | 2,336 | MEDIUM | 2 |
| Model/LLM | model_routes, assistant_routes, copilot_routes | 2,764 | MEDIUM | 2 |
| Cookbook | cookbook_routes, cookbook_helpers, cookbook_output | 4,110 | MEDIUM | 2 |
| Chat/Agent | chat_routes, chat_helpers, (+shell/codex/skills?) | 6,365 | HIGH | 3 |

## Open calls deferred to plan-time (not silently assumed)

- **Chat/Agent shape:** shell/codex/skills are standalone (no shared helpers). Move into
  `routes/chat/` as a theme, or leave flat and package only chat_routes+chat_helpers?
  Recommendation: leave shell/codex/skills flat. Settle at 03-01 planning.
- **Themed groupings:** Calendar+Contacts and Model+Assistant+Copilot have no shared
  `_helpers` — they're co-location groupings. Confirm co-locating vs separate packages at
  plan time (02-01, 02-02).

---
_Required pre-planning grounding for v0.1 phases 1–3. Supersedes the initial roadmap's
Phase 1 (ai_interaction.py) and Phase 2–5 groupings._
