"""Guard test for the routes/auth/ package split (Slice 2,
architecture-runtime-inventory).

routes/auth_routes.py, routes/api_token_routes.py, and routes/device_flow.py
became compatibility shims over the new routes/auth/ package. This pins:

  - the old and new import paths resolve to the exact same module object
    (a true alias, not a copy of its names) for all three modules — this is
    what makes attribute patches applied via the old path visible to code
    living in the new module, and vice versa
  - a representative public symbol from each of the three old modules is the
    SAME object when imported via the old path vs. the new path
  - the api_token_routes pop-and-reimport interaction (also exercised by
    test_api_token_routes.py, which pops "routes.api_token_routes" from
    sys.modules and re-imports it) re-aliases to the canonical module rather
    than creating a detached copy
  - routes/device_flow.py stays importable via `from routes.device_flow import
    ...`, since routes/chatgpt_subscription_routes.py and
    routes/copilot_routes.py depend on that exact path
  - app.py's auth + api-token routers (now wired to routes.auth.routes /
    routes.auth.api_token_routes) still register working FastAPI routers
"""
import os
import sys
import tempfile
from pathlib import Path

_tmp_data = Path(tempfile.mkdtemp(prefix="odysseus_auth_shim_"))
os.environ.setdefault("DATA_DIR", str(_tmp_data))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp_data / 'app.db'}")

from fastapi import APIRouter

import routes.auth
import routes.auth_routes as old_routes
import routes.auth.routes as new_routes
import routes.api_token_routes as old_api_token_routes
import routes.auth.api_token_routes as new_api_token_routes
import routes.device_flow as old_device_flow
import routes.auth.device_flow as new_device_flow

from core.auth import AuthManager


def test_old_routes_path_is_the_same_module_object_as_new_routes_path():
    assert old_routes is new_routes
    assert old_routes.setup_auth_routes is new_routes.setup_auth_routes
    assert old_routes.SESSION_COOKIE is new_routes.SESSION_COOKIE
    assert old_routes.LoginRequest is new_routes.LoginRequest


def test_old_api_token_routes_path_is_the_same_module_object_as_new_path():
    assert old_api_token_routes is new_api_token_routes
    assert old_api_token_routes.setup_api_token_routes is new_api_token_routes.setup_api_token_routes
    assert old_api_token_routes.DEFAULT_SCOPES is new_api_token_routes.DEFAULT_SCOPES


def test_old_device_flow_path_is_the_same_module_object_as_new_path():
    assert old_device_flow is new_device_flow
    assert old_device_flow.create_device_flow_router is new_device_flow.create_device_flow_router
    assert old_device_flow.PendingDeviceFlowStore is new_device_flow.PendingDeviceFlowStore


def test_attribute_assignment_via_old_routes_path_is_visible_via_new_path():
    # Regression pin: many existing tests patch attributes on the OLD import
    # path (e.g. "routes.auth_routes.asyncio") and expect that to affect code
    # that lives inside the moved implementation. That only works if old and
    # new paths are literally the same module object (see the alias tests
    # above) — this test exercises that end-to-end via a real attribute
    # assignment, not a mock.
    original = old_routes.SESSION_COOKIE
    try:
        old_routes.SESSION_COOKIE = "patched-cookie-name"
        assert new_routes.SESSION_COOKIE == "patched-cookie-name"
    finally:
        old_routes.SESSION_COOKIE = original


def test_api_token_routes_pop_and_reimport_realiases_to_canonical_module():
    # Regression pin for the same pop-and-reimport interaction exercised by
    # test_api_token_routes.py: removing "routes.api_token_routes" from
    # sys.modules and re-importing it must re-execute the shim and re-alias
    # to the same canonical module object, not create a detached copy.
    sys.modules.pop("routes.api_token_routes", None)
    import routes.api_token_routes as reimported
    assert reimported is routes.auth.api_token_routes


def test_device_flow_still_importable_via_old_path_for_external_callers():
    # routes/chatgpt_subscription_routes.py and routes/copilot_routes.py both
    # do `from routes.device_flow import (...)`; this must keep working.
    from routes.device_flow import DeviceFlowStart, create_device_flow_router
    assert DeviceFlowStart is new_device_flow.DeviceFlowStart
    assert create_device_flow_router is new_device_flow.create_device_flow_router


def test_setup_auth_routes_registers_a_working_router(tmp_path):
    auth_manager = AuthManager(str(tmp_path / "auth.json"))
    router = new_routes.setup_auth_routes(auth_manager)
    assert isinstance(router, APIRouter)
    assert router.prefix == "/api/auth"
    assert len(router.routes) > 0


def test_setup_api_token_routes_registers_a_working_router():
    router = new_api_token_routes.setup_api_token_routes()
    assert isinstance(router, APIRouter)
    assert router.prefix == "/api"
    assert len(router.routes) > 0
