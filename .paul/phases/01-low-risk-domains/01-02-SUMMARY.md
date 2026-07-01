---
phase: 01-low-risk-domains
plan: 02
subsystem: routes
tags: [refactor, sys-modules-shim, fastapi, auth-domain, slice-2]
requires:
  - phase: 01-01 (document domain) + email/gallery/research precedent
    provides: proven sys.modules alias packaging + source-path repoint discipline
provides:
  - routes/auth/ package (routes.py + api_token_routes.py + device_flow.py) behind compat shims
  - tests/test_auth_package_shim.py guard (identity + pop-reimport + external device_flow importer)
affects: [all later Slice-2 domain plans]
tech-stack:
  added: []
  patterns: [sys.modules alias shim, per-domain package, non-prefixed members keep stem]
key-files:
  created: [routes/auth/__init__.py, routes/auth/routes.py, routes/auth/api_token_routes.py, routes/auth/device_flow.py, tests/test_auth_package_shim.py]
  modified: [routes/auth_routes.py (shim), routes/api_token_routes.py (shim), routes/device_flow.py (shim), app.py]
key-decisions:
  - "Non-prefixed members (api_token_routes, device_flow) keep their stems verbatim (CONVENTIONS rule 3)"
  - "Ship the pure move; roadmap the shim-exposed test_auth_regressions subset fragility (full suite/CI green)"
patterns-established:
  - "Shim changes pop-and-reimport semantics: popping a shim no longer re-execs the underlying (already-cached) real module — can expose test fixtures that assumed re-exec re-established a dependency"
duration: ~12min (implementer) + Qualify
completed: 2026-07-01
---

# SUMMARY — 01-02: Auth domain → routes/auth/

_Executed 2026-07-01 on branch `refactor/routes-auth-domain` (off dev @ document-merged)._

## Result: APPLY complete — Tasks 1 & 2 built by Coding Team Implementer, Task 3 Qualify by orchestrator

| Task | Status | Qualify |
|------|--------|---------|
| 1 — Create `routes/auth/` package + 3 shims + repoint app.py | DONE | PASS |
| 2 — Guard test `tests/test_auth_package_shim.py` | DONE | PASS (7 tests) |
| 3 — Validate at baseline parity (full suite) | DONE_WITH_CONCERNS → resolved | PASS (0 new failures) |

## What changed

- `routes/auth_routes.py` → `routes/auth/routes.py` (byte-identical; 836 ln primary router).
- `routes/api_token_routes.py` → `routes/auth/api_token_routes.py` (stem kept — CONVENTIONS rule 3).
- `routes/device_flow.py` → `routes/auth/device_flow.py` (stem kept).
- **No intra-package import repoints needed** — the three modules do not import each other under the old
  flat paths (verified by grep); bodies are byte-identical.
- `routes/auth/__init__.py` re-exports the public API (setup_auth_routes, SESSION_COOKIE,
  setup_api_token_routes, the Pydantic request models, DeviceFlow* + PendingDeviceFlowStore +
  create_device_flow_router) — derived by grepping every `from routes.<oldpath> import …` in tests + routes.
- All three old flat paths recreated as `sys.modules` alias shims (email pattern).
- `app.py` repointed (2 import lines: setup_auth_routes/SESSION_COOKIE and setup_api_token_routes).
- New `tests/test_auth_package_shim.py` (7 tests): identity ×3, attribute-visibility, api_token
  pop-and-reimport regression, device_flow external-importer path, router checks for both setups.

## Wrinkles handled

- **`device_flow` shim is load-bearing** — imported outside the auth domain by
  `routes/chatgpt_subscription_routes.py` **and** (newly found, beyond GROUND.md) `routes/copilot_routes.py:31`.
  Both keep working via the shim, untouched.
- **`test_api_token_routes.py` pop-and-reimport** — passes; the email-style alias shim re-aliases on re-exec.

## Concern surfaced + decision (in-scope, transparent)

The implementer flagged (DONE_WITH_CONCERNS) that making `routes.auth_routes` a shim changes pop-and-reimport
semantics: `test_auth_policy.py` pops the module and clears `core.auth` repeatedly; previously popping the flat
module forced a re-exec that re-ran `from core.auth import RESERVED_USERNAMES, …` (re-establishing `core.auth`),
but popping a shim does not re-exec the already-cached real module. Running the auth test **files as a narrow
subset** now ImportErrors in `test_auth_regressions.py` (its `_ensure_stub` fixture assumes `core.auth` is loaded).

**Qualify (full suite) settled it: 1 failed, 4265 passed, 5 skipped — the 1 failure is the pre-existing
`TestDockerLoopbackRewrite` docker-env baseline. 0 new failures.** The full suite and CI (`pytest -q`, full
collection) establish `core.auth` for real, so the artifact does not surface there.

**Decision (user-approved, option 1):** ship the pure behavior-preserving move; roadmap the fixture hardening as
a deferred follow-up (recorded in STATE.md Deferred Issues). Not fixed here to keep the PR a clean one-domain
byte-identical move and avoid editing an out-of-scope test file.

## Verification (final)

- `python -m compileall` — clean (package, 3 shims, app.py, chatgpt_subscription_routes.py).
- Targeted: `test_auth_package_shim.py` + `test_api_token_routes.py` + `test_device_flow_routes.py` — 30 passed.
- Runtime identity — `routes.auth_routes is routes.auth.routes` (+ api_token_routes + device_flow) → True/True/True.
- Full suite — **4265 passed, 1 pre-existing failure, 0 new**.

## Files modified (for reconciliation)

routes/auth/__init__.py, routes/auth/routes.py, routes/auth/api_token_routes.py, routes/auth/device_flow.py,
routes/auth_routes.py (shim), routes/api_token_routes.py (shim), routes/device_flow.py (shim), app.py,
tests/test_auth_package_shim.py. Impl commit `2775358`.

## Next

UNIFY → per-PR Codex review on the diff → PR to `dev`. Then Phase 1 complete (both low-risk domains shipped);
next milestone work is Phase 2 (medium-risk: calendar/contacts, model, cookbook).
