"""Guard test for the routes/model/ package split (Slice 2,
architecture-runtime-inventory, Phase 2 / 02-02).

routes/model_routes.py, routes/assistant_routes.py, and
routes/copilot_routes.py became compatibility shims over the new
co-located routes/model/ package (routes.py, assistant.py, copilot.py),
packaged as ONE domain (copilot.py has a real, if fail-and-swallowed,
intra-domain edge to model). This pins:

  - the old and new import paths resolve to the exact same module object
    (a true alias, not a copy of its names) — this is what makes attribute
    patches applied via the old path visible to code living in the new
    module, and vice versa
  - a representative public symbol from each of the three old modules is
    the SAME object when imported via the old path vs. the new path
  - a real attribute assignment via an old path is visible via the new path
  - sys.modules.pop + re-import re-aliases to the canonical submodule
  - app.py's model, assistant, and copilot routers (now wired to
    routes.model.routes / routes.model.assistant / routes.model.copilot)
    still register working FastAPI routers
"""
import os
import sys
import tempfile
from pathlib import Path

_tmp_data = Path(tempfile.mkdtemp(prefix="odysseus_model_shim_"))
os.environ.setdefault("DATA_DIR", str(_tmp_data))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp_data / 'app.db'}")

from fastapi import APIRouter

import routes.model_routes as old_model
import routes.model.routes as new_model
import routes.assistant_routes as old_assistant
import routes.model.assistant as new_assistant
import routes.copilot_routes as old_copilot
import routes.model.copilot as new_copilot


def test_old_model_path_is_the_same_module_object_as_new_model_path():
    assert old_model is new_model
    assert old_model.setup_model_routes is new_model.setup_model_routes
    assert old_model._probe_endpoint is new_model._probe_endpoint
    assert old_model._visible_models is new_model._visible_models


def test_old_assistant_path_is_the_same_module_object_as_new_assistant_path():
    assert old_assistant is new_assistant
    assert old_assistant.setup_assistant_routes is new_assistant.setup_assistant_routes
    assert old_assistant._crew_to_dict is new_assistant._crew_to_dict


def test_old_copilot_path_is_the_same_module_object_as_new_copilot_path():
    assert old_copilot is new_copilot
    assert old_copilot.setup_copilot_routes is new_copilot.setup_copilot_routes
    assert old_copilot._provision_endpoint is new_copilot._provision_endpoint


def test_attribute_assignment_via_old_model_path_is_visible_via_new_path():
    # Regression pin: existing tests patch attributes on the OLD import path
    # (e.g. "routes.model_routes._SPEECH_ENDPOINT_SETTINGS"). That only works
    # if old and new paths are literally the same module object (see the
    # identity test above) — this exercises that end-to-end via a real
    # attribute assignment, not a mock.
    original = old_model._speech_settings_using_endpoint
    try:
        old_model._speech_settings_using_endpoint = "patched-value"
        assert new_model._speech_settings_using_endpoint == "patched-value"
    finally:
        old_model._speech_settings_using_endpoint = original


def test_attribute_assignment_via_old_copilot_path_is_visible_via_new_path():
    original = old_copilot._DEVICE_FLOW_STORE
    try:
        old_copilot._DEVICE_FLOW_STORE = "patched-value"
        assert new_copilot._DEVICE_FLOW_STORE == "patched-value"
    finally:
        old_copilot._DEVICE_FLOW_STORE = original


def test_pop_and_reimport_realiases_model_to_canonical_module():
    sys.modules.pop("routes.model_routes", None)
    try:
        reimported = __import__("routes.model_routes", fromlist=["setup_model_routes"])
        assert reimported is new_model
    finally:
        sys.modules["routes.model_routes"] = new_model


def test_pop_and_reimport_realiases_assistant_to_canonical_module():
    sys.modules.pop("routes.assistant_routes", None)
    try:
        reimported = __import__("routes.assistant_routes", fromlist=["setup_assistant_routes"])
        assert reimported is new_assistant
    finally:
        sys.modules["routes.assistant_routes"] = new_assistant


def test_pop_and_reimport_realiases_copilot_to_canonical_module():
    sys.modules.pop("routes.copilot_routes", None)
    try:
        reimported = __import__("routes.copilot_routes", fromlist=["setup_copilot_routes"])
        assert reimported is new_copilot
    finally:
        sys.modules["routes.copilot_routes"] = new_copilot


def test_setup_model_routes_registers_a_working_router():
    router = new_model.setup_model_routes(model_discovery=None)
    assert isinstance(router, APIRouter)
    assert router.prefix == "/api"
    assert len(router.routes) > 0


def test_setup_assistant_routes_registers_a_working_router():
    router = new_assistant.setup_assistant_routes(task_scheduler=None)
    assert isinstance(router, APIRouter)
    assert router.prefix == "/api/assistant"
    assert len(router.routes) > 0


def test_setup_copilot_routes_registers_a_working_router():
    router = new_copilot.setup_copilot_routes()
    assert isinstance(router, APIRouter)
    assert router.prefix == "/api/copilot"
    assert len(router.routes) > 0
