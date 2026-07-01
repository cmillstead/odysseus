## My Assumptions for Phase 2: Medium-risk domains (Calendar/Contacts, Model, Cookbook)

_Phase-scoped assumptions. Milestone-level grounding lives in `.paul/GROUND-v0.1.md`; this narrows to the
three Phase-2 domains, starting with 02-01._

### Technical Approach

- Reuse the shipped `sys.modules` alias-shim pattern (gallery/research/email/document/auth) — no new tools, no
  design decisions on the mechanism. File move + shim + `__init__.py` re-export.
- File-naming per `.paul/CONVENTIONS.md`: `<domain>_routes.py`→`routes.py`; non-prefixed members keep stems.
- Move bodies byte-identical; repoint only intra-package imports (if any) + docstring paths.
- Medium-risk = larger files + heavier test coupling (more patch targets, more source-path introspection tests)
  than Phase 1, plus a package-SHAPE question for the two "themed grouping" domains (no shared `_helpers`).

### Implementation Order

1. **02-01 Calendar/Contacts** first — two independent files, cleanest of the three; warms Phase 2.
2. **02-02 Model/LLM** — three standalone files (model/assistant/copilot); shape TBD at plan time.
3. **02-03 Cookbook** — genuine shared cluster (routes + helpers + output), 188 KB main file; largest, last.
- One domain per plan / per PR.

### Scope Boundaries

**In scope (02-01):** package `routes/calendar/` and `routes/contacts/`; shims at old flat paths;
`__init__.py` re-exports; guard test(s); repoint the 6 calendar source-path CONTENT tests.
**Out of scope:** any logic change; touching other route files; renaming symbols; the Model/Cookbook domains
(separate plans); the Chat/Agent domain (Phase 3).
**Ambiguous → resolved:** calendar+contacts package shape (co-locate vs separate) → **two separate packages**
(GROUND.md; zero shared code).

### Risk Areas

- **Source-path introspection tests** — 6 calendar tests read `routes/calendar_routes.py` source by path (incl.
  `test_model_helper_owner_scope.py`, which also bit 01-01). Must repoint to `routes/calendar/routes.py`.
- **delitem/pop + reimport tests** — `test_calendar_owner_scope.py` (delitem+`__import__`) and
  `test_carddav_password_encryption.py` (`sys.modules.pop`) must survive via the alias shim (re-exec re-aliases).
- **String-path patch targets** — `mock.patch("routes.contacts_routes.SETTINGS_FILE"/DATA_DIR/...)` require the
  old path to be the SAME object as the new (the whole point of the alias shim).
- **Cross-domain consumers** — `src/tools/{calendar,contacts,notes}.py`, `src/caldav_sync.py`,
  `routes/codex_routes.py`, `routes/email/helpers.py` import calendar/contacts symbols; all preserved via shim.
- PEP-420 namespace shadowing → run tests with `PYTHONPATH` + `python -P`.

### Dependencies

**From prior phases:** none — pattern proven on five domains; Phase 1 (Documents/Auth) shipped.
**External:** none (no new packages).
**Feeds into:** 02-02, 02-03 reuse the same convention + shim recipe + source-path audit discipline.

---
_Validated: 2026-07-01. Required before /paul:discover, /paul:ground, and /paul:plan._
