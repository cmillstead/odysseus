"""Email route domain, split by module (Slice 2, architecture-runtime-inventory).

    routes/email/routes.py   — FastAPI route handlers + `setup_email_routes()`
    routes/email/helpers.py  — IMAP/SMTP helpers, account config, Pydantic models
    routes/email/pollers.py  — background loops (auto-summarize, scheduled send)

``routes.email_routes`` / ``routes.email_helpers`` / ``routes.email_pollers``
re-export from here for backward compatibility (old import paths keep working).
"""
from routes.email.routes import setup_email_routes  # noqa: F401
from routes.email.pollers import _start_poller  # noqa: F401
from routes.email.helpers import (  # noqa: F401
    EmailNotConfiguredError,
    SendEmailRequest, ExtractStyleRequest,
    make_oauth_state, verify_oauth_state,
    require_owner, require_user,
    attachment_extract_dir,
    DATA_DIR, SETTINGS_FILE, ATTACHMENTS_DIR, COMPOSE_UPLOADS_DIR, SCHEDULED_DB,
    OWNER_SCOPED_EMAIL_CACHE_TABLES,
)
