# SUMMARY — Phase 3 / 03-01: Chat/Agent

_Applied 2026-07-04 on branch `codex/phase3-chat-agent`. Domain 9 of 9, last
v0.1 Backend Module Boundaries domain._

## What shipped

One focused `routes/chat/` package behind two `sys.modules` alias shims,
behavior-preserving:

- `routes/chat_routes.py` -> `routes/chat/routes.py` (chat API routes).
- `routes/chat_helpers.py` -> `routes/chat/helpers.py` (shared chat helpers).
- `routes/chat/__init__.py` is docstring-only, with no eager re-exports.
- Old flat paths remain as shims:
  - `routes.chat_routes is routes.chat.routes`
  - `routes.chat_helpers is routes.chat.helpers`
- `app.py` now imports `setup_chat_routes` from `routes.chat.routes`.
- `shell_routes.py`, `codex_routes.py`, and `skills_routes.py` intentionally stay flat:
  they are standalone singleton route surfaces, not part of the shared chat
  helper cluster.
- Added root `AGENTS.md` because this repo previously had none; it records the
  repo-level branch, shim, verification, and roadmap rules for future agents.

## Tests

- Added `tests/test_chat_package_shim.py` to pin old/new module identity,
  representative symbol identity, old-path attribute visibility, pop/reimport
  re-aliasing, and canonical `app.py` wiring.
- Repointed source-path introspection tests from old shim files to canonical
  implementation files:
  - chat route readers -> `routes/chat/routes.py`
  - chat helper readers -> `routes/chat/helpers.py`
- Kept runtime imports and patch targets on old paths where appropriate; those
  are the compatibility contract the shims preserve.

## Validation

- Focused chat/package cluster: `50 passed`.
- Python compile check clean for moved modules, shims, and `app.py`.
- Broad route/chat regression bundle: `262 passed`.
- Full suite, sandboxed: `4297 passed, 5 skipped, 3 failed` — failures were
  sandbox-local socket bind denials in `tests/test_chroma_client.py`, so the
  same command was rerun with escalation.
- Full suite, escalated: `4299 passed, 5 skipped, 1 failed`; the sole failure is
  the documented pre-existing docker-env baseline
  `tests/test_model_routes.py::TestDockerLoopbackRewrite::test_rewrites_loopback_when_in_docker`.
- Repo-wide `ruff check` ran but fails on the existing lint baseline (`874`
  findings, mostly longstanding `E402` / unused-import findings). Narrow ruff
  on the new chat shims, package marker, guard test, and touched source-reader
  tests passed.

## Deltas from Plan/Ground

- Open call resolved to the recommended narrow package shape:
  `routes/chat/` = chat routes + chat helpers only.
- No behavior or import-contract changes intended.

## Result

Phase 3 / 03-01 completes the last v0.1 Slice 2 multi-file route domain.
