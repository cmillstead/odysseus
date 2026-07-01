# DISCOVERY — Phase 1: Low-risk domains (Documents, Auth)

_Level-1 quick discovery. The overall approach is settled (shipped email/gallery/research
shim pattern); this records the few genuine technical decisions for THIS phase._

## Technical approach (decided)

**Packaging via `sys.modules` alias shim** — the proven, behavior-preserving pattern from
the email domain (fork PR #2). Old flat path becomes a shim that re-execs
`from routes.<domain> import <mod> as _real; sys.modules[__name__] = _real`, so old and new
import paths are the *same module object*. No new libraries, no framework choices — this is a
file-move + shim, not a design problem.

## Decision 1 — file-naming convention

**Chosen** (recorded durably in `.paul/CONVENTIONS.md`):
- `<domain>_routes.py` → `routes/<domain>/routes.py`
- `<domain>_<suffix>.py` → `routes/<domain>/<suffix>.py` (helpers/pollers/output)
- domain members without the `<domain>_` prefix keep their stem verbatim
- `__init__.py` re-exports public API; old paths → shims

**Considered & rejected:** renaming non-prefixed members (e.g. `api_token_routes.py` →
`api_token.py`). Rejected — extra churn and surprise for no clarity gain; the shim maps old→new
regardless, so shortening buys nothing. Minimal-rename wins.

## Decision 2 — Documents shape

`document_routes.py` + `document_helpers.py` → `routes/document/{routes,helpers}.py`.
`document_helpers` has no external importers (internal to document_routes) but is shimmed for
consistency. No wrinkles. **Lowest risk → plan 01-01 (first).**

## Decision 3 — Auth shape + two shim wrinkles surfaced

`auth_routes.py` (primary) + `api_token_routes.py` + `device_flow.py` → `routes/auth/`
(`routes.py`, `api_token_routes.py`, `device_flow.py`).

Two non-obvious findings that make Auth the *second* plan, not the first:
1. **`device_flow` is imported outside the auth domain** — `routes/chatgpt_subscription_routes.py`
   does `from routes.device_flow import …`, and chatgpt_subscription is a singleton staying
   flat. → the `routes/device_flow.py` shim is **load-bearing**, not optional.
2. **`test_api_token_routes.py` does `sys.modules.delitem(...)` + reimport** — the shim must
   survive pop-and-reimport (re-exec re-aliases to the canonical module). Same interaction the
   email security-regression test exercised; known-good under the pattern, but must be verified
   green explicitly.

## Unknowns remaining

None blocking. Both domains are mechanical moves with a proven pattern; the wrinkles above are
identified and covered by shims + explicit test runs. No research phase needed.

---
_Level-1 discovery complete → grounding (GROUND.md) → plan._
