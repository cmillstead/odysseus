# SUMMARY — Phase 2 / 02-03: Cookbook

_Applied 2026-07-04 on branch `refactor/routes-cookbook-domain` (commits `d604b36`, `9d4fcb0`). Domain 8 of 9 (last Phase-2 / MEDIUM domain). PR to `dev` pending._

## What shipped
One co-located `routes/cookbook/` package behind three `sys.modules` alias shims, behavior-preserving — the mechanically SIMPLEST Phase-2 move (the 02-01/02-02 shim-reload gotcha is ABSENT here; GROUND verified no cookbook test evicts/reloads these modules):
- `routes/cookbook_routes.py` → `routes/cookbook/routes.py` (3,501 ln, **byte-identical** — `git diff bd32ccb:… HEAD:…` empty).
- `routes/cookbook_helpers.py` → `routes/cookbook/helpers.py` (1,365 ln, **byte-identical**).
- `routes/cookbook_output.py` → `routes/cookbook/output.py` (75 ln, **byte-identical**).
- `routes/cookbook/__init__.py` = **docstring only, NO eager re-exports** (an eager `from .routes import …` would pull fastapi/shell_routes/auth/middleware at package-import time for no benefit; consumers use the old flat paths via shims).
- Old flat paths recreated as `sys.modules` alias shims (email/model precedent): `routes.cookbook_routes is routes.cookbook.routes`, `routes.cookbook_helpers is routes.cookbook.helpers`, `routes.cookbook_output is routes.cookbook.output`.
- The two intra-domain imports in `routes/cookbook/routes.py` (`:33` `from routes.cookbook_output import …`, `:40` `from routes.cookbook_helpers import …`) left **byte-identical** — resolve via the sibling shims; no cycle (helpers/output import neither sibling). `:32` `from routes.shell_routes import TMUX_LOG_DIR` untouched (external dep).
- `app.py:721` repointed `from routes.cookbook_routes import setup_cookbook_routes` → `from routes.cookbook.routes import setup_cookbook_routes` (`:722` include_router unchanged).

## Tests
- Repointed **9 source-path introspection literals across 4 test files**, in TWO construction forms (the segment-joined form was the Codex-caught risk a slash-only grep misses):
  - Form (a) slash-joined (5): `test_security_regressions.py:135`, `test_cookbook_dependency_completion_regression.py:12`, `test_cookbook_cpu_only_serve.py:20/122/155`.
  - Form (b) segment-joined (4): `test_cookbook_helpers.py:336/349/589/723` → `… / "routes" / "cookbook" / "routes.py"`.
  - `test_cookbook_deps_recipes.py` untouched (its `:8` mention is prose, reads a `.js` file). Post-edit basename audit (`cookbook_(routes|helpers|output)\.py`) clean of functional flat-path reads.
- Added `tests/test_cookbook_package_shim.py` (guard test): identity for all 3 old↔new paths, attribute-visibility, `sys.modules.pop`+reimport re-alias, and router asserts BOTH `/api/cookbook/ssh-key` AND `/api/model/serve` present (NO single prefix — cookbook has a mixed-prefix router, unlike model).

## Validation
- Full suite: **4292 passed, 5 skipped, 1 failed** — the sole failure is the pre-existing unrelated `test_model_routes.py::TestDockerLoopbackRewrite` (docker-env). **0 new failures vs baseline.**
- `python -m compileall` clean on all touched files.
- No change to `tests/helpers/import_state.py` or any reload-site test (the shim-reload gotcha does not apply — GROUND verified, confirmed empty in the diff).
- Internal audit (spec + simplify + harden) + feature QA: all **PASS, zero findings**.
- Codex diff review: **PASS, no defects** — ran its own live probe confirming old↔new module identity, `from`-import source module, and `mock.patch("routes.cookbook_helpers.X")` visibility through both paths; guard test `8 passed`.

## Deltas from PLAN/GROUND
- None material. Byte-identical move as planned; the optional cosmetic top-of-file path comment was NOT added (kept strictly byte-identical — none of the three files had an existing path comment to update).
- Guard test uses `sys.modules.pop` (PLAN-sanctioned equivalent to `monkeypatch.delitem`).
- Pre-existing ruff findings in the moved bodies (E402 import-scatter, one F401 in helpers) left as-is per the byte-identical-move boundary. The guard test's `E402` matches the accepted pattern in `test_model_package_shim.py` (imports follow `os.environ.setdefault`).

## Out-of-scope observations (deferred, not fixed in this PR)
- `tests/test_cookbook_deps_recipes.py:8` prose comment names `routes/cookbook_routes.py`, now stale relative to the physical layout — inert (descriptive text, no file read); left untouched per the byte-identical-move boundary. Sweep at inventory/state-sync time.
- `specs/architecture-runtime-inventory.md` and `.paul/*` still reference old flat cookbook paths — synced through the PAUL loop (this SUMMARY + STATE), consistent with 02-02 where the inventory doc was likewise not updated per-domain.
