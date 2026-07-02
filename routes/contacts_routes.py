"""
routes/contacts_routes.py — compatibility shim (Slice 2, #architecture-runtime-inventory).

The real implementation moved to ``routes/contacts/routes.py``. This module is
aliased to that module object (via ``sys.modules``) rather than copying its
names, so ``from routes.contacts_routes import X``, ``import routes.contacts_routes
as X``, and ``mock.patch("routes.contacts_routes.X", ...)`` all keep working
identically for every existing caller — including patches that need to
affect code living inside the real module, since old and new paths now
resolve to the exact same module object (not a copy of its names).
Behavior-preserving: no logic lives in this file.
"""
import sys

from routes.contacts import routes as _real

sys.modules[__name__] = _real
