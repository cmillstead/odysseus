"""Guard test for the routes/calendar/ and routes/contacts/ package splits
(Slice 2, architecture-runtime-inventory, Phase 2 / 02-01).

routes/calendar_routes.py and routes/contacts_routes.py became compatibility
shims over the new routes/calendar/ and routes/contacts/ packages, packaged
as two SEPARATE domains (no shared code between them). This pins:

  - the old and new import paths resolve to the exact same module object
    (a true alias, not a copy of its names) — this is what makes attribute
    patches applied via the old path visible to code living in the new
    module, and vice versa
  - a representative public symbol from each old module is the SAME object
    when imported via the old path vs. the new path
  - sys.modules.pop + re-import re-aliases to the canonical package module
  - app.py's calendar and contacts routers (now wired to routes.calendar.routes
    and routes.contacts.routes) still register working FastAPI routers
"""
import os
import sys
import tempfile
from pathlib import Path

_tmp_data = Path(tempfile.mkdtemp(prefix="odysseus_calendar_contacts_shim_"))
os.environ.setdefault("DATA_DIR", str(_tmp_data))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp_data / 'app.db'}")

from fastapi import APIRouter

import routes.calendar_routes as old_calendar
import routes.calendar.routes as new_calendar
import routes.contacts_routes as old_contacts
import routes.contacts.routes as new_contacts


def test_old_calendar_path_is_the_same_module_object_as_new_calendar_path():
    assert old_calendar is new_calendar
    assert old_calendar.setup_calendar_routes is new_calendar.setup_calendar_routes
    assert old_calendar.EventCreate is new_calendar.EventCreate
    assert old_calendar._parse_dt is new_calendar._parse_dt


def test_old_contacts_path_is_the_same_module_object_as_new_contacts_path():
    assert old_contacts is new_contacts
    assert old_contacts.setup_contacts_routes is new_contacts.setup_contacts_routes
    assert old_contacts._fetch_contacts is new_contacts._fetch_contacts
    assert old_contacts._parse_vcards is new_contacts._parse_vcards


def test_attribute_assignment_via_old_calendar_path_is_visible_via_new_path():
    # Regression pin: existing tests patch attributes on the OLD import path
    # (e.g. "routes.calendar_routes.SETTINGS_FILE"). That only works if old
    # and new paths are literally the same module object (see the identity
    # test above) — this exercises that end-to-end via a real attribute
    # assignment, not a mock.
    original = old_calendar._ensure_positive_duration
    try:
        old_calendar._ensure_positive_duration = "patched-value"
        assert new_calendar._ensure_positive_duration == "patched-value"
    finally:
        old_calendar._ensure_positive_duration = original


def test_attribute_assignment_via_old_contacts_path_is_visible_via_new_path():
    original = old_contacts.SETTINGS_FILE
    try:
        old_contacts.SETTINGS_FILE = "patched-value"
        assert new_contacts.SETTINGS_FILE == "patched-value"
    finally:
        old_contacts.SETTINGS_FILE = original


def test_pop_and_reimport_realiases_calendar_to_canonical_module():
    sys.modules.pop("routes.calendar_routes", None)
    try:
        reimported = __import__("routes.calendar_routes", fromlist=["setup_calendar_routes"])
        assert reimported is new_calendar
    finally:
        sys.modules["routes.calendar_routes"] = new_calendar


def test_pop_and_reimport_realiases_contacts_to_canonical_module():
    sys.modules.pop("routes.contacts_routes", None)
    try:
        reimported = __import__("routes.contacts_routes", fromlist=["setup_contacts_routes"])
        assert reimported is new_contacts
    finally:
        sys.modules["routes.contacts_routes"] = new_contacts


def test_setup_calendar_routes_registers_a_working_router():
    router = new_calendar.setup_calendar_routes()
    assert isinstance(router, APIRouter)
    assert router.prefix == "/api/calendar"
    assert len(router.routes) > 0


def test_setup_contacts_routes_registers_a_working_router():
    router = new_contacts.setup_contacts_routes()
    assert isinstance(router, APIRouter)
    assert router.prefix == "/api/contacts"
    assert len(router.routes) > 0
