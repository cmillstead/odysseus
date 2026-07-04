"""Guard test for the routes/cookbook/ package split (Slice 2,
architecture-runtime-inventory, Phase 2 / 02-03).

routes/cookbook_routes.py, routes/cookbook_helpers.py, and
routes/cookbook_output.py became compatibility shims over the new
co-located routes/cookbook/ package (routes.py, helpers.py, output.py),
packaged as ONE domain. This pins:

  - the old and new import paths resolve to the exact same module object
    (a true alias, not a copy of its names) — this is what makes attribute
    patches applied via the old path visible to code living in the new
    module, and vice versa
  - a representative public symbol from each of the three old modules is
    the SAME object when imported via the old path vs. the new path
  - a real attribute assignment via an old path is visible via the new path
  - sys.modules.pop + re-import re-aliases to the canonical submodule
  - app.py's cookbook router (now wired to routes.cookbook.routes) still
    registers a working FastAPI router, exposing both a /api/cookbook/*
    and an /api/model/* route (cookbook has no single shared prefix)
"""
import os
import sys
import tempfile
from pathlib import Path

_tmp_data = Path(tempfile.mkdtemp(prefix="odysseus_cookbook_shim_"))
os.environ.setdefault("DATA_DIR", str(_tmp_data))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp_data / 'app.db'}")

from fastapi import APIRouter

import routes.cookbook_routes as old_routes
import routes.cookbook.routes as new_routes
import routes.cookbook_helpers as old_helpers
import routes.cookbook.helpers as new_helpers
import routes.cookbook_output as old_output
import routes.cookbook.output as new_output


def test_old_routes_path_is_the_same_module_object_as_new_routes_path():
    assert old_routes is new_routes
    assert old_routes.setup_cookbook_routes is new_routes.setup_cookbook_routes


def test_old_helpers_path_is_the_same_module_object_as_new_helpers_path():
    assert old_helpers is new_helpers
    assert old_helpers.load_stored_hf_token is new_helpers.load_stored_hf_token


def test_old_output_path_is_the_same_module_object_as_new_output_path():
    assert old_output is new_output
    assert old_output.error_aware_output_tail is new_output.error_aware_output_tail


def test_attribute_assignment_via_old_helpers_path_is_visible_via_new_path():
    # Regression pin: existing tests patch attributes on the OLD import path
    # (e.g. "routes.cookbook_helpers._validate_repo_id"). That only works if
    # old and new paths are literally the same module object (see the
    # identity test above) — this exercises that end-to-end via a real
    # attribute assignment, not a mock.
    original = old_helpers._SESSION_ID_RE
    try:
        old_helpers._SESSION_ID_RE = "patched-value"
        assert new_helpers._SESSION_ID_RE == "patched-value"
    finally:
        old_helpers._SESSION_ID_RE = original


def test_pop_and_reimport_realiases_routes_to_canonical_module():
    sys.modules.pop("routes.cookbook_routes", None)
    try:
        reimported = __import__("routes.cookbook_routes", fromlist=["setup_cookbook_routes"])
        assert reimported is new_routes
    finally:
        sys.modules["routes.cookbook_routes"] = new_routes


def test_pop_and_reimport_realiases_helpers_to_canonical_module():
    sys.modules.pop("routes.cookbook_helpers", None)
    try:
        reimported = __import__("routes.cookbook_helpers", fromlist=["load_stored_hf_token"])
        assert reimported is new_helpers
    finally:
        sys.modules["routes.cookbook_helpers"] = new_helpers


def test_pop_and_reimport_realiases_output_to_canonical_module():
    sys.modules.pop("routes.cookbook_output", None)
    try:
        reimported = __import__("routes.cookbook_output", fromlist=["error_aware_output_tail"])
        assert reimported is new_output
    finally:
        sys.modules["routes.cookbook_output"] = new_output


def test_setup_cookbook_routes_registers_a_working_router():
    router = new_routes.setup_cookbook_routes()
    assert isinstance(router, APIRouter)
    assert len(router.routes) > 0
    paths = {r.path for r in router.routes}
    assert "/api/cookbook/ssh-key" in paths
    assert "/api/model/serve" in paths
