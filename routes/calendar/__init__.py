"""Calendar route domain (Slice 2, architecture-runtime-inventory).

    routes/calendar/routes.py   — FastAPI route handlers + `setup_calendar_routes()`

``routes.calendar_routes`` re-exports from here for backward compatibility
(old import path keeps working).
"""
from routes.calendar.routes import (  # noqa: F401
    setup_calendar_routes,
    EventCreate,
    EventUpdate,
    parse_due_for_user,
    _parse_dt,
    _parse_dt_pair,
    _ics_escape,
    _safe_ics_filename,
    _ics_naive_dtstart,
    _ensure_positive_duration,
    set_user_tz_offset,
    _ensure_default_calendar,
    _resolve_base_uid,
    _push_caldav_event_after_commit,
    _record_caldav_delete_tombstone,
)
