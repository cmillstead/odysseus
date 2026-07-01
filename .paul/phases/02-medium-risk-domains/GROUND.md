# GROUND — Phase 2 / 02-01: Calendar + Contacts

_Re-derived from the live tree 2026-07-01 per `.paul/CONVENTIONS.md` (spec numbers not trusted)._
_Decision: **two separate packages** (`routes/calendar/`, `routes/contacts/`) — user-approved 2026-07-01._

## Files (re-derived line counts)
- `routes/calendar_routes.py` — **1,591 ln**
- `routes/contacts_routes.py` — **900 ln**
- **Total 2,491 ln** (spec §4 said 2,336 — 155 undercount; files grew)

No `calendar_helpers.py` / `contacts_helpers.py` / shared `_helpers` exists.

## Cross-coupling — NONE (decisive for the two-package shape)
- `grep contacts routes/calendar_routes.py` → 0; `grep calendar routes/contacts_routes.py` → 0.
- No shared module; different stacks — Calendar: `core.database`, `src.auth_helpers`, `src.user_time`, `dateutil.rrule`; Contacts: `httpx`, `core.log_safety`, `core.middleware.require_admin`, `src.url_safety`, `src.constants`.
- All imports in both files are absolute → **zero intra-package import repoints** needed after the move.

## External references (must stay working via shim)
Calendar:
- `app.py:712` — `from routes.calendar_routes import setup_calendar_routes`
- `routes/codex_routes.py:432` → `EventCreate`
- `src/tools/notes.py:126,199` → `parse_due_for_user`
- `src/tools/calendar.py:21` → multi-symbol `from routes.calendar_routes import (…)`
- `src/caldav_sync.py:277` → `_ensure_positive_duration`

Contacts:
- `app.py:801` — `from routes.contacts_routes import setup_contacts_routes`
- `routes/email/helpers.py:1552,1652` → `_fetch_contacts` (function-level import)
- `src/tools/contacts.py:33,92` → `from routes import contacts_routes as cc` (function-level)

Setup signatures: `setup_calendar_routes() -> APIRouter` (prefix `/api/calendar`); `setup_contacts_routes()` (prefix `/api/contacts`).

`__init__.py` public API to re-export —
- `routes/calendar/__init__.py`: `setup_calendar_routes`, `EventCreate`, `EventUpdate`, `parse_due_for_user`, `_parse_dt`, `_ics_escape`, `_safe_ics_filename`, `_ics_naive_dtstart`, `_ensure_positive_duration`, `set_user_tz_offset`, `quick_parse` (+ any symbol `src/tools/calendar.py:21` imports — union at build time).
- `routes/contacts/__init__.py`: `setup_contacts_routes`, `_parse_vcards`, `_fetch_contacts`.

## Source-path introspection CONTENT tests → MUST be repointed (CONVENTIONS, 01-01 lesson)
All reference **calendar** source by file path; repoint `"routes/calendar_routes.py"` → `"routes/calendar/routes.py"`:
- `tests/test_caldav_bidirectional_sync.py:44` — `Path("routes/calendar_routes.py").read_text()` (asserts substrings :47-53)
- `tests/test_caldav_url_hardening.py:171` — `Path("routes/calendar_routes.py").read_text(...)` (asserts :173-177)
- `tests/test_model_helper_owner_scope.py:23` — `_function_source("routes/calendar_routes.py", "quick_parse")`
- `tests/test_upload_limits_centralized.py:91` AND `:105` — two dicts keyed `"routes/calendar_routes.py"`, read via `(REPO/path).read_text()`
- `tests/test_direct_upload_limits.py:50` — dict keyed `"routes/calendar_routes.py"`, read via `_source(path)`

**No** source-path CONTENT test reads `contacts_routes.py`. (Benign docstring/comment hits — not source reads: `test_calendar_cli_overlap.py:3`, `test_checkin_digest_owner_scope.py:6`, `test_calendar_recurrence.py:4`, `test_notes_update_due_date.py:24`.)

## Shim-critical patch/registry tests (must keep working via alias shim)
- `tests/test_carddav_password_encryption.py` — `mock.patch("routes.contacts_routes.SETTINGS_FILE"/DATA_DIR/LOCAL_CONTACTS_FILE)`; `sys.modules.pop("routes.contacts_routes", None)`.
- `tests/test_calendar_owner_scope.py:184-185` — `monkeypatch.delitem(sys.modules, "routes.calendar_routes")` + `__import__("routes.calendar_routes", …)`.
- Fake-module injections (temporary replace — unaffected by shim): `test_notes_update_due_date.py:66-68`, `tests/cli/test_contacts_cli_rows.py:9-13`.
- `import routes.calendar_routes as` / `routes.contacts_routes as` aliases across ~9 tests + `tests/helpers/calendar_routes.py`.

## Full-suite Qualify cluster to watch
Calendar/CalDAV/ICS (~23 + `tests/helpers/calendar_routes.py`): test_calendar_*, test_caldav_*, test_ics_*, test_parse_due_time_first, test_user_time, test_model_helper_owner_scope, test_upload_limits_centralized, test_direct_upload_limits, test_notes_update_due_date, test_checkin_digest_owner_scope, test_null_owner_gates.
Contacts/CardDAV/vCard (7): test_carddav_password_encryption, test_contacts_carddav_security, test_vcard_unfolding, test_contacts_add_null_name, test_contacts_vcard_parse, test_contacts_import_nonstring, tests/cli/test_contacts_cli_rows.

## Convention applied
Two packages: `routes/calendar/routes.py` (← calendar_routes.py) + `routes/contacts/routes.py` (← contacts_routes.py); `__init__.py` re-exports each public API; old flat paths → `sys.modules` alias shims; bodies byte-identical; 6 calendar source-path tests repointed; app.py two lines repointed.

---
_Pre-planning gate satisfied for 02-01 (grounded from live tree; open call resolved: two packages)._
