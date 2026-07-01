"""
routes/device_flow.py — compatibility shim (Slice 2, #architecture-runtime-inventory).

The real implementation moved to ``routes/auth/device_flow.py``. This
module is aliased to that module object (via ``sys.modules``) rather than
copying its names, so ``from routes.device_flow import X``, ``import
routes.device_flow as X``, and ``mock.patch("routes.device_flow.X", ...)``
all keep working identically for every existing caller — including patches
that need to affect code living inside the real module, since old and new
paths now resolve to the exact same module object (not a copy of its
names). This shim is load-bearing: ``routes/chatgpt_subscription_routes.py``
and ``routes/copilot_routes.py`` import from this path and stay flat.
Behavior-preserving: no logic lives in this file.
"""
import sys

from routes.auth import device_flow as _real

sys.modules[__name__] = _real
