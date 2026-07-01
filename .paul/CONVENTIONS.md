# Conventions — Odysseus Backend Refactor

Durable cross-plan conventions for this refactor. Referenced by every route-domain PLAN.

## Route-domain package naming (Slice 2)

When packaging a flat route domain into `routes/<domain>/`:

1. **`<domain>_routes.py` → `routes/<domain>/routes.py`** — the domain's main router
   (holds `setup_<domain>_routes()`).
2. **`<domain>_<suffix>.py` → `routes/<domain>/<suffix>.py`** — files sharing the domain
   prefix drop it: `_helpers.py`→`helpers.py`, `_pollers.py`→`pollers.py`,
   `_output.py`→`output.py`. (Matches the shipped email/gallery precedent.)
3. **Domain members NOT prefixed with `<domain>_` keep their stem verbatim** — e.g. under
   `routes/auth/`, `api_token_routes.py` stays `api_token_routes.py` and `device_flow.py`
   stays `device_flow.py`. We only shorten names that would be redundant with the folder;
   we do NOT rename unrelated files (less churn, less surprise).
4. **`routes/<domain>/__init__.py`** re-exports the public API (`setup_<domain>_routes` +
   the symbols external callers/tests import) for convenience.
5. **Every original flat path becomes a `sys.modules` alias shim** —
   `from routes.<domain> import <mod> as _real; sys.modules[__name__] = _real`. This makes
   the old path resolve to the *exact same module object*, so `import`, `from … import`,
   `importlib.import_module`, and `mock.patch("routes.<oldname>.X")` / `monkeypatch.setattr`
   all keep working — including tests that `sys.modules.pop(...)` then re-import.
6. **Move bodies byte-identical** — only repoint intra-package imports and docstring path
   references. No logic changes in a packaging PR.

Worked example (Auth):
```
routes/auth/__init__.py            (re-exports setup_auth_routes, SESSION_COOKIE, …)
routes/auth/routes.py              ← auth_routes.py
routes/auth/api_token_routes.py    ← api_token_routes.py   (no auth_ prefix → kept verbatim)
routes/auth/device_flow.py         ← device_flow.py        (kept verbatim)
routes/auth_routes.py              → shim (sys.modules alias)
routes/api_token_routes.py         → shim
routes/device_flow.py              → shim   (load-bearing: chatgpt_subscription imports it)
```

## Spec numbers are ESTIMATES — re-derive at plan time (do NOT trust)

`specs/architecture-runtime-inventory.md` (§2/§4/§6) reports line counts, file lists,
importer counts, and risk levels that are a **Phase-0 snapshot** and have drifted. They are
**inputs for orientation, not ground truth.**

**Rule:** at plan time for each domain, RE-DERIVE the actual numbers from the live tree —
`wc -l` the real files, `grep` the real importers/patch-targets, confirm the real file list —
and plan against *those*. Record the re-derived figures in the phase `GROUND.md`.

Evidence this matters (2026-07-01, Phase 1):
- Spec said Auth = 1,171 ln; actual = **1,238** (836+209+193).
- Spec said Documents = 1,954 ln; actual = **1,967** (1,725+242).
- Spec §4 bucketed shell/codex/skills under "Chat/Agent" as if clustered; they are actually
  **standalone single files** with no shared helpers.

If a plan's risk/size framing rests on a spec number, the plan is ungrounded until that
number is re-derived and cited from the codebase.

---
*Created 2026-07-01. Applies to all Slice 2 domain PRs.*
