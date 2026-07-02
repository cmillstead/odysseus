# SUMMARY — Phase 2 / 02-01: Calendar + Contacts

_Shipped 2026-07-01 (fork PR #5, merge `5907c96`). Domain 6 of 9._

## What shipped
Two separate packages behind `sys.modules` alias shims, behavior-preserving:
- `routes/calendar_routes.py` → `routes/calendar/routes.py` (1,591 ln, **byte-identical**).
- `routes/contacts_routes.py` → `routes/contacts/routes.py` (900 ln, byte-identical bar one docstring self-reference line).
- `routes/calendar/__init__.py` re-exports the calendar public API (GROUND base list ∪ the symbols `src/tools/calendar.py` imports: `_ensure_default_calendar`, `_parse_dt_pair`, `_resolve_base_uid`, `_push_caldav_event_after_commit`, `_record_caldav_delete_tombstone`). **`quick_parse` dropped** — it is a closure inside `setup_calendar_routes()`, not a module-level symbol (the test that references it reads source by path, does not import it).
- `routes/contacts/__init__.py` re-exports `setup_contacts_routes`, `_parse_vcards`, `_fetch_contacts`.
- Old flat paths recreated as `sys.modules` alias shims (email precedent).
- `app.py:712` / `:801` repointed to `routes.calendar.routes` / `routes.contacts.routes`.

## Tests
- Repointed 6 calendar source-path introspection tests (`test_caldav_bidirectional_sync`, `test_caldav_url_hardening`, `test_model_helper_owner_scope`, `test_upload_limits_centralized` ×2, `test_direct_upload_limits`). Contacts had none.
- Added `tests/test_calendar_contacts_package_shim.py` (identity, attribute-visibility, delitem/pop re-alias, `/api/calendar` + `/api/contacts` router prefixes).

## Regression found and fixed (in-scope, same session)
`tests/test_calendar_owner_scope.py::_import_calendar_routes` installs a fake `core.database`, then `delitem`+reimports the route module expecting a **full re-execution** to bind the stub. Under the alias shim, reimporting the old flat path only re-runs the 4-line shim and re-fetches the already-cached real module — the stub never took effect (6 failures under full-suite ordering).
Fix: delete the canonical `routes.calendar.routes` from `sys.modules` and import it by its **dotted name** (not through the shim). Importing via the shim's `from routes.calendar import routes` would NOT force the reload — `_handle_fromlist` skips reimport when the package object still holds the `routes` attribute.
**Carry-forward:** any test using "swap a dependency + delitem/reimport the target" will hit this. Watch `02-02` (Model) and `02-03` (Cookbook).

## Validation
- Full suite: **4273 passed, 5 skipped, 1 failed** — the sole failure is the pre-existing unrelated `test_model_routes.py::TestDockerLoopbackRewrite` (docker-env). 0 new failures vs baseline.
- `python -m compileall` clean on all touched files.
- Codex review (`--base dev`): no actionable correctness issues; runtime probe confirmed both old paths resolve to the canonical package modules.
- ruff on touched files: only pre-existing `E402` ambient noise (not a CI gate).

## Deltas from PLAN/GROUND
- `quick_parse` removed from the calendar `__init__` union (closure, not importable) — the only deviation from the GROUND symbol list.
- Guard test uses `sys.modules.pop` (PLAN-sanctioned equivalent to `monkeypatch.delitem`).
- `test_calendar_owner_scope.py` added to the change set (not in the original `files_modified`) to fix the shim-induced regression.
