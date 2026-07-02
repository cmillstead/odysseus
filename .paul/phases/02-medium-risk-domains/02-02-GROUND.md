# GROUND — Phase 2 / 02-02: Model/LLM (model + assistant + copilot)

_Re-derived from the live tree 2026-07-01 per `.paul/CONVENTIONS.md` (spec numbers not trusted)._
_Shape RESOLVED 2026-07-01 (user): **(A) one co-located `routes/model/` package** — `routes.py` (model) + `assistant.py` + `copilot.py`, three shims at old flat paths. copilot→model is intra-package._

## Files (re-derived line counts)
- `routes/model_routes.py` — **2,442 ln**
- `routes/assistant_routes.py` — **326 ln**
- `routes/copilot_routes.py` — **173 ln**
- **Total 2,941 ln** (ROADMAP §Phase-2 said 2,764 — 177 undercount; files grew)

No `model_helpers.py` / `assistant_helpers.py` / `copilot_helpers.py` exists — these are three standalone flat files (the "themed grouping of standalone files" the ROADMAP predicted).

## Cross-coupling — NOT zero (differs decisively from 02-01)
The zero-shared-code test does **not** come back clean here:
- `grep model_routes/copilot_routes in assistant_routes.py` → **0** — assistant is fully standalone.
- `grep assistant_routes/copilot_routes in model_routes.py` → **0** — model imports neither.
- `copilot_routes.py:95` → **`from routes.model_routes import _invalidate_models_cache`** (function-level, inside a best-effort `try`). One real intra-domain edge: **copilot → model**.

No shared helper module; distinct stacks (model = endpoint/DB management + LLM probing; assistant = task-scheduler-driven; copilot = GitHub device-flow OAuth via `src/copilot.py`). So: **model is a hub, copilot a leaf that borrows one private helper, assistant independent.**

## `model_routes` is a hub — external consumers (all must keep working via shim)
- `routes/chat_routes.py:34` → `from routes.model_routes import _visible_models` (**module-level** — loads model on chat import)
- `routes/chatgpt_subscription_routes.py:101` → `_invalidate_models_cache` (fn-level)
- `routes/cookbook_routes.py:1229, 1290` → `_probe_endpoint` (fn-level)
- `routes/copilot_routes.py:95` → `_invalidate_models_cache` (fn-level, in-domain)
- `src/service_health.py:359` → `from routes.model_routes import _probe_endpoint as probe` (fn-level)
- Consumed private symbols verified module-level in `model_routes.py`: `_invalidate_models_cache` (:1108), `_probe_endpoint`, `_visible_models`.
- Docstring/comment-only mentions (NOT imports): `src/model_context.py:28`, `src/tls_overrides.py:31`, `src/copilot.py:17,139`, `core/auth.py:64` (`_SYNTHETIC_OWNERS` note re assistant).

`assistant_routes` / `copilot_routes` have **no** external importers beyond `app.py` (and copilot's own model edge).

## Setup signatures + app.py wiring + router prefixes
| Module | Setup fn | app.py | Router prefix |
|--------|----------|--------|---------------|
| model | `setup_model_routes(model_discovery)` (:1096) | `app.py:658` import, `:659` `include_router(setup_model_routes(model_discovery))` | **`/api`** (broad — not `/api/model`) |
| copilot | `setup_copilot_routes()` (:166) | `app.py:662` import, `:663` include | `/api/copilot` |
| assistant | `setup_assistant_routes(task_scheduler)` (:80) | `app.py:705` import, `:706` include | `/api/assistant` |

**Note:** model's prefix is the bare `/api` — a guard test should assert prefix `/api` + >0 routes, not `/api/model`.

## Source-path introspection CONTENT tests → MUST be repointed (CONVENTIONS, 01-01/02-01 lesson)
Both read **model** source by path; repoint `"routes/model_routes.py"` → `"routes/model/routes.py"` (assuming canonical lands at `routes/model/routes.py`):
- `tests/test_tls_overrides_scope.py:41` — `ALLOWED_CALLERS` frozenset entry, matched against `_grep_files` output (repo-relative paths). After the move the real caller is `routes/model/routes.py`; the shim has no httpx calls, so it won't match — the test FAILS unless the allowlist entry is repointed.
- `tests/test_live_strip_email_tool_fences.py:28` — `_ROUTES_SRC = Path("routes/model_routes.py")`, later `.read_text()`.
- **No** source-path CONTENT test reads `assistant_routes.py` or `copilot_routes.py`. Benign docstring/comment hits only: `test_null_owner_gates.py:228`, `test_auth_package_shim.py:19,90`, `test_copilot_routes.py:1`.

## ⚠️ Shim-reload gotcha — LANDS IN A SHARED HELPER (the big 02-02 risk)
The 02-01 carry-forward hits here, and worse — it lives in a shared test helper, not one test file.

`tests/helpers/import_state.py::clear_fake_endpoint_resolver_modules()` (:101-142) hardcodes, when `src.endpoint_resolver` is a *fake* stub, `clear_module("routes.model_routes")` (+ any extras), and the callers then re-`import routes.model_routes` to force a fresh load under the *real* resolver:
- `tests/test_model_routes.py:20` calls it, then `import routes.model_routes` + a big `from routes.model_routes import (...~20 privates...)` (:34-59).
- `tests/test_endpoint_probing.py:30` wraps its body in `preserve_import_state("core.database","src.database","core.session_manager","routes.model_routes")`, calls it (:33), then reimports (:47-59).

Under the alias shim, `clear_module("routes.model_routes")` pops only the 4-line shim alias (+ its `routes` parent attr). The canonical `routes.model.routes` stays cached (bound to the fake resolver). The subsequent `import routes.model_routes` re-runs the shim (`from routes.model import routes as _real`), which re-fetches the still-cached canonical module — **the eviction is defeated; model stays bound to the fake `endpoint_resolver`.** (Same root cause as 02-01: `from pkg import mod` won't reload if the package object still holds the attr.)

**Fix (plan into 02-02):**
1. `clear_fake_endpoint_resolver_modules` (and `clear_module` usage for the moved module) must ALSO `clear_module("routes.model.routes")` — clearing the canonical `sys.modules` entry AND its parent attr on `routes.model` forces the shim's `from routes.model import routes` to truly re-execute under the real resolver.
2. `test_endpoint_probing.py`: add `"routes.model.routes"` to `preserve_import_state(...)` so the fresh reimport doesn't leak the canonical module to later tests.
3. `tests/test_helpers_import_state.py` unit-tests the helper with **injected fakes** (`types.ModuleType("routes.model_routes")`, e.g. :305-306, :326-329) — it does NOT import the real module, so adding a `clear_module("routes.model.routes")` (no-op when absent) won't break it; optionally add a covering assertion that the canonical name is cleared too.

`test_model_routes.py` itself does NOT delitem+reimport (it installs the `core.database` stub only `if "core.database" not in sys.modules` and imports once) — so it's safe *except* through the shared helper above.

## `__init__.py` public API to re-export (if a package holds the routes module)
- model: `setup_model_routes`, `_invalidate_models_cache`, `_probe_endpoint`, `_visible_models` (the cross-module-consumed set; the ~20 privates that `test_model_routes.py`/`test_endpoint_probing.py` import resolve via the shim on the old path and need no `__init__` entry — but union any that a non-test consumer imports).
- assistant: `setup_assistant_routes`.
- copilot: `setup_copilot_routes`.

## Anti-pattern flags (P5/P6/P7/P10/P15/P21)
- **P5/P7 (API/helper sig):** setup sigs + `_invalidate_models_cache() -> None` (no args; callers call bare) verified — no drift.
- **P6 (data-access path):** copilot→model helper path verified (`copilot_routes.py:95-96`).
- **P15 (short-circuit guard):** `clear_fake_endpoint_resolver_modules` fires only when `endpoint_resolver.__file__` is falsy (fake). The shim silently defeats its eviction — this is the guard that breaks (see gotcha above).
- **P21 (transport naming):** router prefixes verified (`/api`, `/api/assistant`, `/api/copilot`).
- **P1/P10:** N/A — pure move, no data-model/schema references.

## Shape decision — RESOLVED: (A) co-located `routes/model/`
**Decided 2026-07-01 (user): shape (A).** `routes/model/routes.py` (← model_routes.py), `routes/model/assistant.py` (← assistant_routes.py), `routes/model/copilot.py` (← copilot_routes.py); three shims at the old flat paths; copilot→model is intra-package (`from routes.model.routes import _invalidate_models_cache`). `app.py` repoints: `:658` → `routes.model.routes`, `:662` → `routes.model.copilot`, `:705` → `routes.model.assistant`. The 2 source-path tests repoint to `routes/model/routes.py`.

_Rationale kept for the record —_ applying the 02-01 rule literally (no shared helper module → separate) pointed to three separate packages. But two facts complicated it vs the calendar/contacts case:
- There IS an intra-domain import edge (copilot→model) — though the shim handles it either way, and it's one fn-level private import.
- The ROADMAP names a single `routes/model/` themed package, and all three are LLM-adjacent.

**Two viable shapes:**
- **(A) One co-located `routes/model/` package** — submodules `routes/model/routes.py` (model), `routes/model/assistant.py`, `routes/model/copilot.py`; three shims at the old flat paths; copilot→model becomes intra-package. Matches ROADMAP intent; groups the LLM surface.
- **(B) Three separate packages** — `routes/model/`, `routes/assistant/`, `routes/copilot/`, each `routes.py` + `__init__` + shim. Matches the 02-01 mechanical precedent exactly; copilot→model repointed to canonical (or left via shim).

Coupling mechanics are identical under both (the shim preserves every old path). The choice is organizational. **Recommendation: (A) one `routes/model/` package** — the roadmap already scoped it as one domain, the three are LLM-adjacent, and co-location makes the one real edge intra-package. Needs user confirmation (it sets `files_modified`).

## Planning implications
- Canonical target path assumed `routes/model/routes.py` for the model file regardless of shape (A puts assistant/copilot as siblings; B gives them their own packages). Repoint the 2 source-path tests to whatever the model canonical path is.
- The shared-helper shim fix (`tests/helpers/import_state.py`) is IN SCOPE and must be in `files_modified` — this is the highest-risk item and the reason 02-02 is heavier than 02-01.
- Full-suite Qualify must specifically watch: `test_model_routes.py` (incl. the known-pre-existing `TestDockerLoopbackRewrite` docker failure — unchanged baseline), `test_endpoint_probing.py`, `test_helpers_import_state.py`, `test_copilot_routes.py`, `test_chatgpt_subscription_routes.py`, `test_tls_overrides_scope.py`, `test_live_strip_email_tool_fences.py`, and `chat_routes` (module-level `_visible_models` import).

---
_Pre-planning gate: grounded from live tree. Remaining OPEN CALL: co-locate (A) vs separate (B) — resolve with user, then /paul:plan 02-02._
