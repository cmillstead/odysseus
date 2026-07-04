# GROUND — Phase 2 / 02-03: Cookbook (routes + helpers + output)

_Re-derived from the live tree 2026-07-04 per `.paul/CONVENTIONS.md` (spec numbers not trusted)._
_Domain 8 of 9 (third/last Phase-2 MEDIUM domain). OPEN CALL below: co-locate (A) vs separate (B) — resolve with user, then /paul:plan 02-03._

## Files (re-derived line counts)
- `routes/cookbook_routes.py` — **3,501 ln**
- `routes/cookbook_helpers.py` — **1,365 ln**
- `routes/cookbook_output.py` — **75 ln**
- **Total 4,941 ln** — the LARGEST domain in the milestone (vs Model 2,941 / Calendar+Contacts smaller).

## Cross-coupling — REAL shared code (decisively co-locate, unlike 02-01/02-02)
This is the first domain where the zero-shared-code test comes back **dirty** — there is a genuine internal DAG:
- `cookbook_routes.py:33` → `from routes.cookbook_output import (error_aware_output_tail, classify_dead_download, HF_CACHE_COMPLETE_PROBE, HF_CACHE_INCOMPLETE_PROBE)` — **module-level**.
- `cookbook_routes.py:40` → `from routes.cookbook_helpers import (…~40 symbols…)` — **module-level** (validators, serve-cmd builders, `ServeRequest`, `ModelDownloadRequest`, `load_stored_hf_token`, …).
- `cookbook_helpers.py` imports NEITHER sibling — only stdlib + `fastapi`/`pydantic` + `routes._validators` + `core.platform_compat`. Its docstring: _"Extracted from cookbook_routes.py; the routes module imports the symbols it needs."_
- `cookbook_output.py` is a **pure, dependency-free leaf** (imports only `re`; docstring says kept FastAPI/SQLAlchemy-free for unit-testing) — two fns: `classify_dead_download`, `error_aware_output_tail`.

**DAG: `routes → {helpers, output}`; helpers and output are independent leaves. No cycles.** Real shared code ⇒ co-location is the unambiguous mechanical answer (the 02-01 rule "shared helper module → co-locate" fires cleanly for the first time).

Also note (external dep, NOT moving): `cookbook_routes.py:32` → `from routes.shell_routes import TMUX_LOG_DIR`.

## External consumers (all must keep working via shims)
- **`cookbook_routes`** — only `app.py:721` (`from routes.cookbook_routes import setup_cookbook_routes`). No non-test/app importer. (Leaf as a provider.)
- **`cookbook_helpers`** — a HUB with external, all **fn-level** consumers:
  - `routes/shell_routes.py:1668` → `_llama_cpp_rebuild_cmd`
  - `routes/codex_routes.py:643, 805` → `ServeRequest`
  - `src/tools/cookbook.py:149` → `load_stored_hf_token`
  - (`src/agent_tools/admin_tools.py:86` = **comment only**, not an import — "Parallel to routes/cookbook_helpers._validate_serve_cmd".)
- **`cookbook_output`** — no external non-test consumer (only `cookbook_routes` + its own tests).

## Setup signature + app.py wiring + router paths
| Module | Setup fn | app.py | Router |
|--------|----------|--------|--------|
| cookbook | `setup_cookbook_routes() -> APIRouter` (**no args**, :65) | `:721` import, `:722` `include_router(setup_cookbook_routes())` (**no prefix**) | `APIRouter(tags=["cookbook"])`, **no `prefix=`** |

⚠️ **Router has no single prefix.** Routes carry **inline full paths spanning TWO namespaces**: `/api/cookbook/*` (ssh-key, setup, …) AND `/api/model/*` (`/api/model/download` :509, `/api/model/cached` :851, `/api/model/serve` :1307). The "cookbook" domain owns model download/serve/cache endpoints. ⇒ a guard test asserts `setup_cookbook_routes()` returns an `APIRouter` with **>0 routes** and representative paths (`/api/cookbook/ssh-key`, `/api/model/serve`) resolve — NOT a `prefix=="/api/cookbook"` assertion.

## Source-path introspection CONTENT tests → MUST be repointed (CONVENTIONS, 01-01/02-01/02-02 lesson)
**9 functional path literals across 4 files** (corrected 2026-07-04 after Codex plan review — the first draft's
slash-only grep missed 4 segment-joined reads in `test_cookbook_helpers.py`; the authoritative audit is by
BASENAME: `grep -rnE "cookbook_(routes|helpers|output)\.py" tests/`, which catches both construction forms).
Two forms — repoint both:
- **(a) slash-joined literal** → `routes/cookbook/<file>.py`:
  - `tests/test_security_regressions.py:135` — `Path("routes/cookbook_routes.py").read_text()`
  - `tests/test_cookbook_dependency_completion_regression.py:12` — `_read("routes/cookbook_routes.py")`
  - `tests/test_cookbook_cpu_only_serve.py:20` — `ROUTES_SRC = ROOT / "routes/cookbook_routes.py"`
  - `tests/test_cookbook_cpu_only_serve.py:155` — `(ROOT / "routes/cookbook_routes.py").read_text()`
  - `tests/test_cookbook_cpu_only_serve.py:122` — `(ROOT / "routes/cookbook_helpers.py").read_text()` → `routes/cookbook/helpers.py`
- **(b) segment-joined `Path(...) / "routes" / "cookbook_routes.py"`** → insert a `"cookbook"` segment, filename becomes `"routes.py"` (`… / "routes" / "cookbook" / "routes.py"`):
  - `tests/test_cookbook_helpers.py:336` (`… .parent.parent / "routes" / "cookbook_routes.py"`)
  - `tests/test_cookbook_helpers.py:349` (same)
  - `tests/test_cookbook_helpers.py:589` (`… .parents[1] / "routes" / "cookbook_routes.py"`)
  - `tests/test_cookbook_helpers.py:723` (same, `routes_src = …`)
- **NOT a change:** `tests/test_cookbook_deps_recipes.py:8` mentions `routes/cookbook_routes.py` in a **docstring comment** only; it reads `static/js/cookbook-deps-recipes.js`. Leave untouched. (`test_run_focus.py:203` writes a tmp file merely named `test_cookbook_helpers.py`; `test_taxonomy.py` maps the test filename — neither reads route source.)

## ✅ Shim-reload gotcha — DOES NOT APPLY (the big de-risk vs 02-02)
The 02-01/02-02 headline risk is **absent** here. Verified three ways:
1. No `test_cookbook_*.py` file appears in the repo-wide list of tests using `preserve_import_state` / `clear_fake_endpoint_resolver_modules` / `importlib.reload` / `sys.modules.pop` / `monkeypatch.delitem`.
2. Direct grep for `sys.modules|importlib.reload|monkeypatch.delitem|delattr|clear_module` across **all** cookbook test files → **0 matches**.
3. The only test that live-imports the module (`tests/test_cookbook_remote_windows_diffusers.py:7`, `import routes.cookbook_routes as cookbook_routes`) is a **plain import** + `setup_cookbook_routes()` router iteration — no evict/reload-under-stub.

⇒ **NO change to `tests/helpers/import_state.py`; NO reload-site edits.** No mock.patch targets either (`patch("routes.cookbook…")` → 0 matches; consistent with the no-mocks rule). Cookbook is mechanically the SIMPLEST Phase-2 domain despite being the largest by line count — it is a clean 3-file move behind 3 shims.

## `__init__.py` — MINIMAL (docstring only), per Model precedent
Unlike Model, every externally-consumed symbol here IS module-level importable (`ServeRequest`, `_diagnose_serve_output`, `load_stored_hf_token`, `_llama_cpp_rebuild_cmd`, `_pip_install_no_cache`, `error_aware_output_tail`, `classify_dead_download`, `setup_cookbook_routes`) — so an eager re-export would not error. **Still keep `__init__` docstring-only:** an eager `from .routes import setup_cookbook_routes` would pull the heavy `routes.py` (fastapi, shell_routes, auth, middleware, …) at package-import time for no benefit. Nobody imports `from routes.cookbook import X`; all consumers use the old flat paths, and the shims alias directly to submodules (`from routes.cookbook import routes as _real`), which only needs the package `__init__` to exist.

## Intra-domain imports in routes.py (:33 output, :40 helpers) — LEAVE byte-identical (resolve via shims)
Recommendation: keep `cookbook_routes.py:33`/`:40` **byte-identical** (`from routes.cookbook_output import …` / `from routes.cookbook_helpers import …`) and let them resolve through the sibling shims (`routes.cookbook_output → routes.cookbook.output`, `routes.cookbook_helpers → routes.cookbook.helpers`). No cycle (helpers/output don't import routes). This preserves the byte-identical-move AC and matches the 02-02 copilot precedent (intra-domain import left as-is via shim). _Alternative (NOT recommended):_ repoint to `from routes.cookbook.helpers/output import …` — breaks byte-identical for no functional gain. Plan-time detail; flag for Codex.

## Anti-pattern flags (P5/P6/P7/P10/P15/P21)
- **P5/P7 (API/helper sig):** `setup_cookbook_routes()` no-arg verified; external helper edges are fn-level imports of module-level symbols — no drift.
- **P6 (data-access path):** helpers-hub edges verified (shell :1668, codex :643/:805, src/tools/cookbook :149).
- **P21 (transport naming):** router has NO prefix; inline paths span `/api/cookbook/*` + `/api/model/*` (documented above).
- **P15 (short-circuit guard):** N/A — no reload guard in play (gotcha absent).
- **P1/P10:** N/A — pure move, no data-model/schema references.

## Shape decision — RECOMMEND (A) co-located `routes/cookbook/`
Real shared code (`routes → helpers + output`) makes co-location the unambiguous answer — the 02-01 rule ("no shared helper → separate; shared helper → co-locate") points cleanly to **one package** for the first time in the milestone.

- **(A) One co-located `routes/cookbook/` package** ⟵ RECOMMENDED
  - `routes/cookbook/routes.py`  ← `cookbook_routes.py` (3,501 ln)
  - `routes/cookbook/helpers.py` ← `cookbook_helpers.py` (1,365 ln)
  - `routes/cookbook/output.py`  ← `cookbook_output.py` (75 ln)
  - `routes/cookbook/__init__.py` = docstring only
  - 3 `sys.modules` alias shims at the old flat paths (`routes.cookbook_routes is routes.cookbook.routes`, etc.)
- **(B) Three separate packages** — contradicted by the shared-code DAG; would scatter a genuinely cohesive domain. Not recommended.

Coupling mechanics are identical under both (shims preserve every old path); the choice is organizational, and here the code structure itself argues for (A).

## Planning implications (heavier by size, lighter by mechanics)
- `files_modified` (under shape A): `routes/cookbook/{__init__,routes,helpers,output}.py`, `routes/cookbook_routes.py`, `routes/cookbook_helpers.py`, `routes/cookbook_output.py` (→ shims), `app.py` (1 line — repoint :721 to `routes.cookbook.routes`), and 4 source-path test files (`test_security_regressions.py`, `test_cookbook_dependency_completion_regression.py`, `test_cookbook_cpu_only_serve.py`, `test_cookbook_helpers.py`) + a new guard test `tests/test_cookbook_package_shim.py`.
- **NO `tests/helpers/import_state.py` change; NO reload-site edits** — the gotcha is absent (verified). This is the key contrast with 02-02.
- App wiring is a single-line repoint (`app.py:721` → `from routes.cookbook.routes import setup_cookbook_routes`).
- Full-suite Qualify must watch: `test_cookbook_*` cluster (helpers, error_feedback, diagnosis, hf_token, error_tail_lines, dead_download_status, cpu_only_serve, dependency_completion_regression, remote_windows_diffusers, deps_recipes), plus the external-consumer files whose fn-level imports route through the shims: `test_shell_routes.py`, `test_codex_routes*` (codex), and `src/tools/cookbook.py` paths. Baseline: same 1 pre-existing docker failure (`test_model_routes.py::TestDockerLoopbackRewrite`).

---
_Pre-planning gate: grounded from live tree 2026-07-04. Remaining OPEN CALL: confirm shape (A) co-located (recommended) vs (B) separate — resolve with user, then /paul:plan 02-03._
