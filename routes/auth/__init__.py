"""Auth route domain, split by module (Slice 2, architecture-runtime-inventory).

    routes/auth/routes.py           — FastAPI route handlers + `setup_auth_routes()`
    routes/auth/api_token_routes.py — API token CRUD routes + `setup_api_token_routes()`
    routes/auth/device_flow.py      — shared OAuth/device-flow route scaffolding

``routes.auth_routes`` / ``routes.api_token_routes`` / ``routes.device_flow``
re-export from here for backward compatibility (old import paths keep working).
"""
from routes.auth.routes import (  # noqa: F401
    setup_auth_routes,
    SESSION_COOKIE,
    LoginRequest,
    SetupRequest,
    SignupRequest,
    ChangePasswordRequest,
    CreateUserRequest,
    DeleteUserRequest,
    RenameUserRequest,
    SetAdminRequest,
    SetOpenRegistrationRequest,
)
from routes.auth.api_token_routes import setup_api_token_routes  # noqa: F401
from routes.auth.device_flow import (  # noqa: F401
    DeviceFlowStart,
    DeviceFlowPoll,
    PendingDeviceFlowStore,
    create_device_flow_router,
)
