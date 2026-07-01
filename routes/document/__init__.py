"""Document route domain (Slice 2, architecture-runtime-inventory).

    routes/document/routes.py   — FastAPI route handlers + `setup_document_routes()`
    routes/document/helpers.py  — Pydantic models, serializers, owner-gating helpers

``routes.document_routes`` / ``routes.document_helpers`` re-export from here for
backward compatibility (old import paths keep working).
"""
from routes.document.routes import setup_document_routes  # noqa: F401
from routes.document.helpers import (  # noqa: F401
    DocumentCreate, DocumentUpdate, DocumentPatch,
    _doc_to_dict, _version_to_dict,
    _verify_doc_owner, _owner_session_filter,
    _slug, _resolve_user_upload_path, _assert_pdf_marker_upload_owned, _derive_title,
    _PDF_RENDER_SCALE,
)
