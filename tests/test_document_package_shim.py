"""Guard test for the routes/document/ package split (Slice 2,
architecture-runtime-inventory).

routes/document_routes.py and routes/document_helpers.py became compatibility
shims over the new routes/document/ package. This pins:

  - the old and new import paths resolve to the exact same module object
    (a true alias, not a copy of its names) — this is what makes attribute
    patches applied via the old path (e.g. the SessionLocal patch several
    document tests use) visible to code living in the new module
  - a representative public symbol from each old module is the SAME object
    when imported via the old path vs. the new path
  - setup_document_routes() still builds a router that registers the
    /api/document endpoints
"""
import os
import tempfile
from pathlib import Path

_tmp_data = Path(tempfile.mkdtemp(prefix="odysseus_document_shim_"))
os.environ.setdefault("DATA_DIR", str(_tmp_data))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp_data / 'app.db'}")

from fastapi import APIRouter

import routes.document_routes as old_routes
import routes.document.routes as new_routes
import routes.document_helpers as old_helpers
import routes.document.helpers as new_helpers


def test_old_routes_path_is_the_same_module_object_as_new_routes_path():
    assert old_routes is new_routes
    assert old_routes.setup_document_routes is new_routes.setup_document_routes


def test_old_helpers_path_is_the_same_module_object_as_new_helpers_path():
    assert old_helpers is new_helpers
    assert old_helpers.DocumentCreate is new_helpers.DocumentCreate
    assert old_helpers._doc_to_dict is new_helpers._doc_to_dict


def test_attribute_assignment_via_old_routes_path_is_visible_via_new_path():
    # Regression pin: document tests patch "routes.document_routes.SessionLocal"
    # and expect that to affect the moved implementation. That only works if old
    # and new paths are literally the same module object. Exercised here with a
    # real attribute assignment (no mock), then restored.
    sentinel = object()
    original = old_routes.SessionLocal
    try:
        old_routes.SessionLocal = sentinel
        assert new_routes.SessionLocal is sentinel
    finally:
        old_routes.SessionLocal = original


def test_setup_document_routes_registers_document_endpoints():
    # session_manager/upload_handler are only used inside route closures, not at
    # registration time, so None is a valid inert argument for this code path.
    router = new_routes.setup_document_routes(None)
    assert isinstance(router, APIRouter)
    paths = [r.path for r in router.routes]
    assert len(paths) > 0
    assert any(p.startswith("/api/document") for p in paths)
