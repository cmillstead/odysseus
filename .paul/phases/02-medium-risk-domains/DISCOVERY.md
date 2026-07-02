# DISCOVERY — Phase 2: Medium-risk domains (Calendar/Contacts, Model, Cookbook)

_Level-1 quick discovery. The packaging approach is settled (shipped gallery/research/email/document/auth
`sys.modules` alias-shim pattern); this records the genuine technical decisions for Phase 2, starting with 02-01._

## Technical approach (decided)

Same behavior-preserving `sys.modules` alias-shim packaging proven across five domains. File move + shim +
`__init__.py` re-export; bodies byte-identical; old dotted paths preserved as same-object aliases so imports and
`mock.patch`/`monkeypatch` targets keep working. No new libraries, no framework choices.

Medium-risk (vs Phase 1) means: larger files, heavier test coupling (more patch targets + source-path
introspection tests), and — for two of the three domains — a **package-shape** question (themed grouping of
standalone files vs separate packages), since those domains have no shared `_helpers`.

## Decision 1 — 02-01 Calendar/Contacts package shape → **TWO SEPARATE PACKAGES** (resolved 2026-07-01)

`calendar_routes.py` + `contacts_routes.py` → `routes/calendar/routes.py` + `routes/contacts/routes.py`
(NOT one co-located `routes/calendar/` package).

**Chosen:** two packages. **Considered & rejected:** one co-located `routes/calendar/` holding both modules.
**Rationale (see GROUND.md step 4):** the two files share ZERO code — no import between them, no shared helper,
two distinct dependency stacks (CalDAV vs CardDAV). Co-locating would group modules that never reference each
other (convenience, not cohesion). Separate packages match the one-package-per-domain convention
(`routes/email/`, `routes/gallery/`, `routes/document/`). Still delivered as the single 02-01 plan/PR.

## Decision 2 — 02-02 Model/LLM shape (DEFERRED to 02-02 plan-time)

`model_routes.py` + `assistant_routes.py` + `copilot_routes.py` — also a themed grouping of standalone files
(no shared `_helpers`). Same co-locate-vs-separate question; settle at 02-02 grounding using the same
zero-shared-code test applied here.

## Decision 3 — 02-03 Cookbook shape (likely co-located; DEFERRED to 02-03 plan-time)

`cookbook_routes.py` (188 KB) + `cookbook_helpers.py` + `cookbook_output.py` — this one DOES have a real shared
`_helpers`/`_output` cluster (prefix-shared), so it packages like document/email into one `routes/cookbook/`.
Confirm at 02-03 grounding.

## Unknowns remaining

None blocking for 02-01. Package shape resolved (two packages). Wrinkles (6 calendar source-path repoints,
delitem/pop patch tests) are identified in GROUND.md and covered by the shim + planned repoint tasks + full-suite
Qualify. No research phase needed.

---
_Level-1 discovery complete → grounding (GROUND.md) → 02-01 plan._
