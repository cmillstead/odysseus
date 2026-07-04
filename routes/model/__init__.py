"""Model/LLM route domain, split by module (Slice 2, architecture-runtime-inventory).

    routes/model/routes.py    — model/provider management routes + `setup_model_routes()`
    routes/model/assistant.py — personal assistant routes + `setup_assistant_routes()`
    routes/model/copilot.py   — GitHub Copilot device-flow login + `setup_copilot_routes()`

``routes.model_routes`` / ``routes.assistant_routes`` / ``routes.copilot_routes``
alias to the submodules above for backward compatibility (old import paths keep
working). This package's ``__init__`` is intentionally minimal — NO eager
re-exports. ``_invalidate_models_cache`` is nested inside ``setup_model_routes``
(not importable at module scope), and several model-only test stubs for
``core.database`` lack ``CrewMember``/``ScheduledTask`` (pulled in by
``routes.model.assistant``), so importing this package must not trigger an
eager import of any submodule.
"""
