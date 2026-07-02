"""Contacts route domain (Slice 2, architecture-runtime-inventory).

    routes/contacts/routes.py   — FastAPI route handlers + `setup_contacts_routes()`

``routes.contacts_routes`` re-exports from here for backward compatibility
(old import path keeps working).
"""
from routes.contacts.routes import (  # noqa: F401
    setup_contacts_routes,
    _parse_vcards,
    _fetch_contacts,
)
