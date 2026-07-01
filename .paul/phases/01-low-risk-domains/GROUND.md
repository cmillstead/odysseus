# GROUND — Phase 1: Low-risk domains (Documents, Auth)

_Re-derived from the live tree 2026-07-01 per `.paul/CONVENTIONS.md` (spec numbers not trusted)._

## Documents domain

**Files (re-derived line counts):**
- `routes/document_routes.py` — 1,725 ln
- `routes/document_helpers.py` — 242 ln
- **Total 1,967 ln** (spec §4 said 1,954)

**External references (must stay working via shim):**
- `app.py:681` — `from routes.document_routes import setup_document_routes`
- Tests patch/import `routes.document_routes` (same-object alias required):
  - `test_document_render_pdf_iframe.py` — `import routes.document_routes as droutes`; patches `routes.document_routes.SessionLocal`
  - `test_document_close_clears_active_route.py` — `import routes.document_routes as droutes`
  - `test_document_session_owner_scope.py` — `import routes.document_routes as droutes`
  - `test_auth_disabled_document_access.py` — `import routes.document_routes as droutes`
- `document_helpers` — no external importers found (used only within document_routes); shim
  it anyway for consistency.

**Verdict:** clean 2-file cluster, prefix-shared. Lowest risk. Canonical → `routes/document/`.

## Auth domain

**Files (re-derived line counts):**
- `routes/auth_routes.py` — 836 ln
- `routes/api_token_routes.py` — 209 ln
- `routes/device_flow.py` — 193 ln
- **Total 1,238 ln** (spec §4 said 1,171 — undercount)

**External references (must stay working via shim):**
- `app.py:203` — `from routes.auth_routes import setup_auth_routes, SESSION_COOKIE`
- `app.py:769` — `from routes.api_token_routes import setup_api_token_routes`
- **`device_flow` is imported outside the auth domain:** `routes/chatgpt_subscription_routes.py:11`
  — `from routes.device_flow import (...)`. chatgpt_subscription is a singleton staying flat,
  so `routes/device_flow.py` shim is **load-bearing**.
- Heavy test coupling on `routes.auth_routes.*`:
  - `test_auth_policy.py`, `test_auth_session_revocation.py`, `test_auth_regressions.py`,
    `test_set_admin.py`, `test_delete_user_invalidates_token_cache.py`,
    `test_auth_event_loop.py` — many `from routes.auth_routes import …`
  - `test_auth_event_loop.py:95` — `monkeypatch.setattr("routes.auth_routes.asyncio.to_thread", …)`
  - `test_integrations_store_shape.py`, `test_rename_user_owner_sync.py`,
    `test_rename_user_token_cache.py`, `test_set_admin.py` — `import routes.auth_routes as ar` + setattr
  - `test_device_flow_routes.py:7` — `from routes import device_flow`; `monkeypatch.setattr(device_flow, "require_admin", …)`
  - **`test_api_token_routes.py:62-64`** — `monkeypatch.delitem(sys.modules, "routes.api_token_routes")`
    then `import routes.api_token_routes as mod`. **Shim-critical**: the pop-and-reimport must
    re-alias to the canonical module (same interaction email's security test exercised).

**Verdict:** 3-file domain; `auth_routes` is the primary, `api_token_routes`/`device_flow`
are non-prefixed members (kept verbatim per convention rule 3). Slightly higher coupling than
Documents (many patch targets), hence 01-02 (after Documents warms the pattern).

## Shim-critical tests to run green (both plans)

- Full `pytest` at baseline parity (baseline: 3 known-unrelated pre-existing failures).
- Specifically: `test_api_token_routes.py` (delitem+reimport), `test_device_flow_routes.py`
  (patch via `routes.device_flow`), and the document `SessionLocal` patch tests.

## Convention applied

Per `.paul/CONVENTIONS.md`: `routes/document/{routes,helpers}.py`;
`routes/auth/{routes.py, api_token_routes.py, device_flow.py}`; `__init__.py` re-exports;
old flat paths → `sys.modules` alias shims; bodies byte-identical.

---
_Pre-planning gate satisfied for Phase 1 (ASSUMPTIONS → DISCOVERY → GROUND complete)._
