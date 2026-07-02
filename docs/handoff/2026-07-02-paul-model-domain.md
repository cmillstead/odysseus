# Handoff — 2026-07-02 — PAUL 02-02 (Model/LLM) reviewed (Codex PASS), ready to APPLY

Written before a context clear. Durable state lives in `.paul/` + committed branch (read those first).

## TL;DR resume
1. `git -C /Users/cevin/src/odysseus status` (clean) and `git log --oneline -6`.
2. On branch **`refactor/routes-model-domain`** (off `dev`; `dev` has Documents+Auth+Calendar/Contacts merged, 6/9).
   Commits ahead: `84e4226` (pre-planning gate: GROUND+PLAN+STATE) + `22f87d5` (plan revised per Codex PASS). NOT pushed, NO PR.
3. **Immediate next: APPLY 02-02** — the plan is written, Codex-reviewed (**3 rounds → PASS**), safe to implement.
   User said "need to clear first" in response to the apply/harness-enforcement question → **confirm then apply**.
4. Flow (identical to how 02-01 shipped): dispatch a **Coding Team Implementer** for Tasks 1-4, then **I run the
   full-suite Qualify (Task 5)**, then **Codex diff review** (`codex review --base dev`), then **push + PR to dev**.

## 02-02 plan — READ `.paul/phases/02-medium-risk-domains/02-02-PLAN.md` + `02-02-GROUND.md` (authoritative)
Shape RESOLVED (user): **(A) ONE co-located `routes/model/` package** — `routes.py` (← model_routes.py 2442 ln),
`assistant.py` (← assistant_routes.py 326 ln), `copilot.py` (← copilot_routes.py 173 ln). All byte-identical moves.
- Three `sys.modules` alias shims at old flat paths (model_routes→routes.model.routes, etc.).
- `routes/model/__init__.py` = **DOCSTRING ONLY, no re-exports** (critical — see gotchas).
- `app.py` repoints: :658→routes.model.routes, :662→routes.model.copilot, :705→routes.model.assistant.
- **copilot.py NOT repointed** (byte-identical).
- Repoint 2 model source-path tests: test_tls_overrides_scope.py:41 (ALLOWED_CALLERS frozenset),
  test_live_strip_email_tool_fences.py:28.
- **Task 3 (headline risk) — shim-reload fix at 5 sites**: shared helper `tests/helpers/import_state.py`
  (clear_fake_endpoint_resolver_modules also `clear_module("routes.model.routes")`) + preserve_import_state adds
  `"routes.model.routes"` in test_endpoint_probing.py:30, test_model_routes.py:17, test_model_defaults.py:9 +
  test_review_regressions.py `_install_model_route_import_stubs` (~:94) needs delitem of BOTH names AND
  `monkeypatch.delattr` of parent attrs (routes.model_routes off routes, routes off routes.model) + a covering
  assertion in test_helpers_import_state.py.
- New guard test `tests/test_model_package_shim.py` (identity + attr-visibility + delitem/pop re-alias for all 3 +
  prefixes /api, /api/assistant, /api/copilot).

## Why Codex FAILED it twice (the lessons — apply to 02-03 Cookbook too)
- **Phantom symbol:** my first GROUND wrongly said `_invalidate_models_cache` is module-level. It is **NESTED**
  inside `setup_model_routes` (model_routes.py:1108, closes over `_models_cache`) → NOT importable. The existing
  `from routes.model_routes import _invalidate_models_cache` in copilot:95 / chatgpt_subscription:101 run inside
  `try/except: pass` and **already fail-and-swallow today** (pre-existing silent no-op). ⇒ don't re-export it; don't
  repoint copilot. `_probe_endpoint` (:768) and `_visible_models` (:1069) ARE module-level.
- **Eager __init__ hazard:** an eager `from .assistant import …` pulls `CrewMember`/`ScheduledTask` at model-shim
  import time; model-only `core.database` stubs (test_model_routes:24-30 lacks CrewMember; test_review_regressions:
  76-82 lacks both) → AttributeError. ⇒ minimal __init__.
- **fromlist short-circuit:** clearing only `sys.modules["routes.model.routes"]` is insufficient where a test
  re-imports via the shim (`from routes.model import routes`) — the `routes.model` package still holds the stale
  `routes` attr. Must ALSO delattr the parent attr. (The shared helper's `clear_module` already does both; raw
  `monkeypatch.delitem` sites do not.)

## Gotchas (same as prior domains)
- **Test invocation:** `PYTHONPATH=/Users/cevin/src/odysseus python3 -P -m pytest <paths>` (PEP-420 shadowing).
- **Baseline:** full suite = **1 pre-existing failure** (`test_model_routes.py::TestDockerLoopbackRewrite`, docker-
  env, unrelated) + everything else green. 0 new = parity.
- **Push hook:** demands a test run AND a linter run before push (full pytest + `ruff check` on touched files;
  ruff shows only pre-existing E402 ambient noise, NOT a CI gate).
- **git hygiene:** one command per Bash call; never `git add -A`; `git mv` for moves. `gh ... --repo cmillstead/odysseus --base dev`.
- **codex exec HANGS on stdin** — always invoke with `< /dev/null` (e.g. `codex exec "…" < /dev/null 2>&1`). Plan
  review used `codex exec` / `codex exec resume <session>`; diff review uses `codex review --base dev`.

## NEW STANDING RULE (global) established this session — NOT yet durably enforced
**Always run `/second-opinion` (Codex review) on the PLAN before APPLY. ALWAYS.** User was emphatic. A memory file
won't enforce it (recall is relevance-gated). **OUTSTANDING TASK:** take this to `/harness-engineer` to bake a hard
gate into the PAUL `/paul:apply` workflow (refuse APPLY without a recorded plan-stage second-opinion PASS), +/- a
hook. Do this before/after 02-02 APPLY per user's call. (User was deciding APPLY-first vs enforcement-first when the
clear was called.)

## After 02-02 merges
Update `.paul/PROJECT.md` (Model/LLM → Validated, 7/9) + `STATE.md`; write `02-02-SUMMARY.md`. Then 02-03 Cookbook
(real shared cluster: cookbook_routes 188 KB + cookbook_helpers + cookbook_output → one `routes/cookbook/`).
