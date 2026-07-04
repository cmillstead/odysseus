"""Guard test for the routes/chat/ package split (Slice 2,
architecture-runtime-inventory, Phase 3 / 03-01).

routes/chat_routes.py and routes/chat_helpers.py became compatibility shims over
the new routes/chat/ package (routes.py, helpers.py). This pins that old and new
import paths resolve to the exact same module objects, so old-path imports and
mock.patch targets keep affecting the real implementation.
"""

import sys
from pathlib import Path

import routes.chat.routes as new_routes
import routes.chat.helpers as new_helpers
import routes.chat_routes as old_routes
import routes.chat_helpers as old_helpers


def test_old_routes_path_is_the_same_module_object_as_new_routes_path():
    assert old_routes is new_routes
    assert old_routes.setup_chat_routes is new_routes.setup_chat_routes


def test_old_helpers_path_is_the_same_module_object_as_new_helpers_path():
    assert old_helpers is new_helpers
    assert old_helpers.build_chat_context is new_helpers.build_chat_context


def test_attribute_assignment_via_old_helpers_path_is_visible_via_new_path():
    original = old_helpers._CASUAL_BLOCKLIST_RE
    try:
        old_helpers._CASUAL_BLOCKLIST_RE = "patched-value"
        assert new_helpers._CASUAL_BLOCKLIST_RE == "patched-value"
    finally:
        old_helpers._CASUAL_BLOCKLIST_RE = original


def test_attribute_assignment_via_old_routes_path_is_visible_via_new_path():
    original = old_routes._IMAGE_MODEL_PREFIXES
    try:
        old_routes._IMAGE_MODEL_PREFIXES = ("patched-image-model",)
        assert new_routes._IMAGE_MODEL_PREFIXES == ("patched-image-model",)
    finally:
        old_routes._IMAGE_MODEL_PREFIXES = original


def test_pop_and_reimport_realiases_routes_to_canonical_module():
    sys.modules.pop("routes.chat_routes", None)
    try:
        reimported = __import__("routes.chat_routes", fromlist=["setup_chat_routes"])
        assert reimported is new_routes
    finally:
        sys.modules["routes.chat_routes"] = new_routes


def test_pop_and_reimport_realiases_helpers_to_canonical_module():
    sys.modules.pop("routes.chat_helpers", None)
    try:
        reimported = __import__("routes.chat_helpers", fromlist=["build_chat_context"])
        assert reimported is new_helpers
    finally:
        sys.modules["routes.chat_helpers"] = new_helpers


def test_app_imports_chat_router_from_canonical_package():
    app_src = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert "from routes.chat.routes import setup_chat_routes" in app_src
