# SUMMARY — Phase 2 / 02-02: Model / LLM

_Applied 2026-07-04 on branch `refactor/routes-model-domain` (commits `9a7cbf3`, `920bfc4`, `f1bb512`, `7d7f9cb`). Domain 7 of 9. PR to `dev` pending._

## What shipped
One co-located `routes/model/` package behind three `sys.modules` alias shims, behavior-preserving:
- `routes/model_routes.py` → `routes/model/routes.py` (2,442 ln, **byte-identical** bar the top-of-file path comment).
- `routes/assistant_routes.py` → `routes/model/assistant.py` (326 ln, byte-identical bar path comment).
- `routes/copilot_routes.py` → `routes/model/copilot.py` (173 ln, byte-identical bar path comment). Its `from routes.model_routes import _invalidate_models_cache` (nested, non-importable symbol; fails-and-swallows today) left **byte-identical** — resolves via the shim, behavior preserved.
- `routes/model/__init__.py` = **docstring only, NO eager re-exports** (an eager import would ImportError on the nested `_invalidate_models_cache`, and an eager `from .assistant import …` would pull `CrewMember`/`ScheduledTask` that model-only test stubs don't provide).
- Old flat paths recreated as `sys.modules` alias shims (email precedent): `routes.model_routes is routes.model.routes`, `routes.assistant_routes is routes.model.assistant`, `routes.copilot_routes is routes.model.copilot`.
- `app.py` `:658`/`:662`/`:705` repointed to `routes.model.routes` / `routes.model.copilot` / `routes.model.assistant`.

## Tests
- Repointed 2 source-path introspection tests: `test_tls_overrides_scope.py:41` (ALLOWED_CALLERS) and `test_live_strip_email_tool_fences.py:28` (`_ROUTES_SRC`) → `"routes/model/routes.py"`.
- Added `tests/test_model_package_shim.py` (128 ln): identity for all 3 old↔new paths, attribute-visibility, `sys.modules.pop`+reimport re-alias, router prefixes `/api` + `/api/assistant` + `/api/copilot`.

## Headline risk handled: shim-reload gotcha across ALL sites
The 02-01 carry-forward landed here inside a **shared helper** plus 4 reload sites. Under the alias shim, clearing only `routes.model_routes` is insufficient — the canonical `routes.model.routes` stays cached (bound to the stubbed dependency), so the reimport re-fetches the stale module. Fixed every site to also clear/preserve the canonical name, removing BOTH the `sys.modules` entry AND the parent attr:
- `tests/helpers/import_state.py::clear_fake_endpoint_resolver_modules` — also `clear_module("routes.model.routes")`.
- `preserve_import_state(...)` in `test_endpoint_probing.py`, `test_model_routes.py`, `test_model_defaults.py` — added `"routes.model.routes"`.
- `test_review_regressions.py::_install_model_route_import_stubs` — `delitem` both sys.modules entries + `delattr` both parent attrs (`model_routes` off `routes`, `routes` off `routes.model`) via monkeypatch (teardown restores).
- `test_helpers_import_state.py` — covering assertion added (inject a `routes.model.routes` fake, assert it is cleared).

## Validation
- Full suite: **4284 passed, 5 skipped, 1 failed** — the sole failure is the pre-existing unrelated `test_model_routes.py::TestDockerLoopbackRewrite` (docker-env). **0 new failures vs baseline.**
- `python -m compileall` clean on all touched files.
- Codex review (`--base dev`): **APPROVED, zero findings** — "did not identify any actionable regressions"; runtime probe confirmed `routes.model_routes is routes.model.routes` and patched attributes resolve through both paths.

## Deltas from PLAN/GROUND
- Implementer also removed 3 pre-existing unused imports (`_PROVIDER_CURATED`, `pytest`, `make_core_db_stub`, `src.auth_helpers`) flagged by ruff in files already being edited — cosmetic, in already-touched files.
- Guard test uses `sys.modules.pop` (PLAN-sanctioned equivalent to `monkeypatch.delitem`).
- `E402` on the new shim test matches the identical pre-existing pattern in both reference shim tests (imports follow `os.environ.setdefault`) — left as-is per convention.

## Applied under override
The live PAUL apply-review gate had no recorded artifact for this plan (the 3-round Codex plan-review predated the recorder). Applied via `override-plan-review 02-02-codex-passed-3-rounds-commit-22f87d5-not-recorded` — logged bypass; the plan WAS Codex-passed (commit `22f87d5`) and the diff was independently Codex-reviewed (above).
