---
phase: 01-low-risk-domains
plan: 01
subsystem: routes
tags: [refactor, sys-modules-shim, fastapi, document-domain, slice-2]
requires:
  - phase: (pattern) email/gallery/research shim precedent
    provides: proven sys.modules alias packaging
provides:
  - routes/document/ package (routes.py + helpers.py) behind compat shims
  - tests/test_document_package_shim.py guard
  - source-path introspection lesson folded into CONVENTIONS.md
affects: [01-02-auth, all later Slice-2 domain plans]
tech-stack:
  added: []
  patterns: [sys.modules alias shim, per-domain package, source-path test repoint]
key-files:
  created: [routes/document/__init__.py, routes/document/routes.py, routes/document/helpers.py, tests/test_document_package_shim.py]
  modified: [routes/document_routes.py, routes/document_helpers.py, app.py, tests/test_model_helper_owner_scope.py, tests/test_vision_owner_scope.py, tests/test_imap_mailbox_quoting.py]
key-decisions:
  - "Repoint source-path introspection tests to canonical file (not shim)"
  - "Fix pre-existing vacuous email_pollers absence-assertion while in the file"
patterns-established:
  - "GROUND must grep source-path literals in tests, not just import/patch refs"
duration: ~20min
completed: 2026-07-01
---

# SUMMARY — 01-01: Documents domain → routes/document/

_Executed 2026-07-01 on branch `refactor/routes-document-domain`._

## Result: APPLY complete — all 3 tasks PASS

| Task | Status | Qualify |
|------|--------|---------|
| 1 — Create `routes/document/` package + shims + repoint app.py | DONE | PASS |
| 2 — Guard test `tests/test_document_package_shim.py` | DONE | PASS (4/4) |
| 3 — Validate at baseline parity | DONE_WITH_CONCERNS → resolved | PASS |

## What changed

- `routes/document_routes.py` → `routes/document/routes.py` (byte-identical; one intra-package
  import repointed to `routes.document.helpers`).
- `routes/document_helpers.py` → `routes/document/helpers.py` (byte-identical).
- `routes/document/__init__.py` — re-exports `setup_document_routes` + helper public API.
- Old paths recreated as `sys.modules` alias shims.
- `app.py:681` repointed to `routes.document.routes`.
- New `tests/test_document_package_shim.py` (4 tests: identity ×2, attribute-visibility, router).

## GAP found and fixed during Task 3 (Qualify caught it)

The first full-suite run had **2 NEW failures** — source-introspection tests that read
`routes/document_routes.py` **by file path** (not import), so they saw the shim, not the moved
source. GROUND.md missed these because they don't `import` the module. Fixed by repointing to
the canonical path (same repoint the email refactor required):
- `tests/test_model_helper_owner_scope.py:17` — `routes/document_routes.py` → `routes/document/routes.py`
- `tests/test_vision_owner_scope.py:91` — `routes/document_routes.py` → `routes/document/routes.py`

## Deviation (in-scope, discovered) — bonus pre-existing fix

- `tests/test_imap_mailbox_quoting.py` — repointed **two** path literals: the document one
  (line 90), AND `routes/email_pollers.py` → `routes/email/pollers.py` (line 86). The email
  line was a **pre-existing vacuous test** left by the email refactor: it uses an *absence*
  assertion, which passes silently against a shim. Fixed while in the file (no-known-broken).

## Verification (final)

- `python -m compileall` — clean (package, shims, app.py).
- Runtime identity — `routes.document_routes is routes.document.routes` (+ helpers). ✓
- Guard test — 4/4 pass.
- Full suite — **1 failed, 4257 passed, 5 skipped**. The 1 failure
  (`test_model_routes.py::TestDockerLoopbackRewrite`) is the documented pre-existing docker-env
  baseline failure, unrelated to documents. **0 new failures.**

## Lesson for UNIFY / future domain plans

**Add a "source-path introspection" grep to per-domain GROUND**: `grep -rn "<oldfile>.py" tests`
for `read_text()`/`_function_source()` path literals, not just `import`/`patch` references.
Several tests assert on route source *by file path*; these must be repointed on every move.
Fold this into `.paul/CONVENTIONS.md` at UNIFY.

## Files modified (for reconciliation)

routes/document/__init__.py, routes/document/routes.py, routes/document/helpers.py,
routes/document_routes.py, routes/document_helpers.py, app.py,
tests/test_document_package_shim.py, tests/test_model_helper_owner_scope.py,
tests/test_vision_owner_scope.py, tests/test_imap_mailbox_quoting.py

## Next

Not yet committed (the refactor commit is separate from the earlier `.paul` chore commit).
UNIFY → commit → per-PR `/second-opinion` on the diff → PR to `dev`.
