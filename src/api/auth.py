"""Simple token-based authentication dependency for the control-bim-pf-engine API."""
import os
from fastapi import Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)


def get_configured_api_key() -> str | None:
    """Retrieve API key from environment if configured."""
    return os.getenv("PF_API_KEY") or os.getenv("API_KEY")


def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> bool:
    """Validate Bearer token or X-API-Key header against configured PF_API_KEY.
    
    If PF_API_KEY is not configured in the environment, authentication is disabled (local dev mode).
    """
    configured_key = get_configured_api_key()
    if not configured_key:
        return True

    token = None
    if credentials:
        token = credentials.credentials
    elif x_api_key:
        token = x_api_key

    if not token or token != configured_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Provide Bearer token or X-API-Key header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True
