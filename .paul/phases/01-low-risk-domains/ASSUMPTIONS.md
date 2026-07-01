## My Assumptions for Phase 1: Low-risk domains (Documents, Auth)

_Phase-scoped assumptions. Milestone-level surfacing + grounding lives in
`.paul/GROUND-v0.1.md`; this narrows to the two Phase-1 domains._

### Technical Approach

- Use the shipped `sys.modules` alias shim pattern (email/gallery/research) — no new tools,
  no design decisions. File move + shim + `__init__.py` re-export.
- File-naming per `.paul/CONVENTIONS.md`: `<domain>_routes.py`→`routes.py`,
  `<domain>_helpers.py`→`helpers.py`, non-prefixed members kept verbatim.
- Move bodies byte-identical; repoint only intra-package imports + docstring paths.

### Implementation Order

1. **01-01 Documents first** — cleanest 2-file, prefix-shared cluster, minimal external
   coupling (only `app.py` + a few `import routes.document_routes as droutes` tests).
2. **01-02 Auth second** — more patch-target coupling and two shim wrinkles (device_flow
   external importer; api_token pop-and-reimport test), so it benefits from Documents
   re-warming the pattern first.
- One domain per plan / per PR.

### Scope Boundaries

**In scope:** package `routes/document/` and `routes/auth/`; shims at all old flat paths;
`__init__.py` re-exports; a guard test per domain pinning old==new module identity.
**Out of scope:** any logic change; touching other route files; the singletons
(chatgpt_subscription stays flat and keeps working via the device_flow shim); renaming
non-prefixed members.
**Ambiguous:** none material for Phase 1 (the themed-grouping and chat/agent open calls are
Phase 2/3 concerns).

### Risk Areas

- **device_flow shim is load-bearing** — chatgpt_subscription_routes imports it from the old
  path; the shim must alias correctly or that route breaks.
- **api_token pop-and-reimport** — `test_api_token_routes.py` deletes the module from
  sys.modules and re-imports; the shim must re-alias on re-exec.
- **Heavy `routes.auth_routes.*` patch targets** across many tests — all preserved iff old
  path is the *same object* as new (the whole point of the alias shim).
- PEP-420 namespace shadowing when running tests from a non-root cwd (use PYTHONPATH + `-P`).

### Dependencies

**From prior phases:** none — pattern already proven on email/gallery/research.
**External:** none (no new packages).
**Feeds into:** Phase 2 (medium domains) reuses the exact convention + shim recipe validated
here.

---
_Validated: 2026-07-01. Required before /paul:discover, /paul:ground, and /paul:plan._
