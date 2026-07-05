# AGENTS.md

Repository-level instructions for AI coding agents working in this repo.

## Scope

These instructions apply to the entire repository unless a more specific
`AGENTS.md` exists in a subdirectory.

## Workflow

- Use a feature branch for all changes. Do not commit directly to `dev`.
- Keep changes behavior-preserving unless the user explicitly asks for behavior
  changes.
- Inspect `git status --short` before editing and before finishing. Do not
  revert or overwrite unrelated user changes.
- Prefer deterministic local work over spawning extra agents. The Claude budget
  may be constrained; Codex-side review/checks are preferred when possible.
- Before claiming completion, run the relevant tests and a lint/static check.
  The commit hook may reject commits if no test and lint run happened in the
  session.

## Route Packaging Pattern

For the backend route-boundary roadmap:

- Single-file route domains normally stay flat.
- Multi-file domains may move into a package, but old flat import paths must
  remain compatibility shims.
- Use the established `sys.modules[__name__] = _real` shim pattern so old and
  new import paths resolve to the exact same module object. This preserves
  `mock.patch("old.path.symbol", ...)` behavior.
- Keep package `__init__.py` files lightweight, usually docstring-only. Avoid
  eager re-exports that import heavy route modules just by importing a package.
- Add a guard test proving old and new paths are the same module object,
  representative symbols are identical, attribute assignment through the old
  path is visible through the new path, and pop/reimport re-aliases correctly.

## Current v0.1 Roadmap Context

- v0.1 is finishing backend route module boundaries.
- Phases 1 and 2 are complete.
- Phase 3 / 03-01 is the final v0.1 domain: Chat/Agent.
- For Phase 3, prefer `routes/chat/` for `chat_routes.py` + `chat_helpers.py`
  only. Leave `shell_routes.py`, `codex_routes.py`, and `skills_routes.py`
  flat unless a fresh grounding pass proves they should move too.

## Verification Baseline

- Full-suite command from the handoff:
  `PYTHONPATH=/Users/cevin/src/odysseus python3 -P -m pytest tests/ -q -p no:cacheprovider`
- Known pre-existing baseline issue: `test_model_routes.py::TestDockerLoopbackRewrite`
  may fail in docker-unavailable environments. Target is zero new failures.
- Run `ruff check` before committing when available.

## Handoff Docs

- `docs/handoff/*.md` and `docs/plans/` may contain user or prior-agent
  handoff state. Leave unrelated untracked handoff docs alone.
