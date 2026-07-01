"""Guard test for the routes/email/ package split (Slice 2,
architecture-runtime-inventory).

routes/email_routes.py, routes/email_helpers.py, and routes/email_pollers.py
became compatibility shims over the new routes/email/ package. This pins:

  - the old and new import paths resolve to the exact same module object
    (a true alias, not a copy of its names) — this is what makes attribute
    patches applied via the old path visible to code living in the new
    module, and vice versa
  - a representative public symbol from each of the three old modules is the
    SAME object when imported via the old path vs. the new path
  - app.py's email router (now wired to the new routes.email.routes path)
    still registers a working FastAPI router at startup
"""
import os
import tempfile
from pathlib import Path

_tmp_data = Path(tempfile.mkdtemp(prefix="odysseus_email_shim_"))
os.environ.setdefault("DATA_DIR", str(_tmp_data))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp_data / 'app.db'}")

from fastapi import APIRouter

import routes.email_routes as old_routes
import routes.email.routes as new_routes
import routes.email_helpers as old_helpers
import routes.email.helpers as new_helpers
import routes.email_pollers as old_pollers
import routes.email.pollers as new_pollers


def test_old_routes_path_is_the_same_module_object_as_new_routes_path():
    assert old_routes is new_routes
    assert old_routes.setup_email_routes is new_routes.setup_email_routes
    assert old_routes._q is new_routes._q
    assert old_routes.SendEmailRequest is new_routes.SendEmailRequest


def test_old_helpers_path_is_the_same_module_object_as_new_helpers_path():
    assert old_helpers is new_helpers
    assert old_helpers._imap_connect is new_helpers._imap_connect
    assert old_helpers._decode_header is new_helpers._decode_header
    assert old_helpers.EmailNotConfiguredError is new_helpers.EmailNotConfiguredError


def test_old_pollers_path_is_the_same_module_object_as_new_pollers_path():
    assert old_pollers is new_pollers
    assert old_pollers._start_poller is new_pollers._start_poller
    assert old_pollers._run_auto_summarize_once is new_pollers._run_auto_summarize_once


def test_attribute_assignment_via_old_helpers_path_is_visible_via_new_path():
    # Regression pin: many existing tests patch attributes on the OLD import
    # path (e.g. "routes.email_helpers._q") and expect that to affect code
    # that lives inside the moved implementation. That only works if old and
    # new paths are literally the same module object (see the alias tests
    # above) — this test exercises that end-to-end via a real attribute
    # assignment, not a mock.
    original = old_helpers._q
    try:
        old_helpers._q = "patched-value"
        assert new_helpers._q == "patched-value"
    finally:
        old_helpers._q = original


def test_setup_email_routes_registers_a_working_router():
    router = new_routes.setup_email_routes()
    assert isinstance(router, APIRouter)
    assert router.prefix == "/api/email"
    assert len(router.routes) > 0
