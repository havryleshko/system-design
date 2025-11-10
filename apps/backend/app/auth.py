"""
Custom authentication for LangGraph API using Supabase JWT tokens.
"""
import os
from functools import lru_cache
from typing import Any, Dict

import jwt
from langgraph_sdk import Auth

auth = Auth()


@lru_cache(maxsize=1)
def get_jwks_client():
    """Get JWKS client for Supabase token validation."""
    jwks_url = os.getenv("SUPABASE_JWKS_URL")
    if not jwks_url:
        raise RuntimeError("SUPABASE_JWKS_URL not configured")
    return jwt.PyJWKClient(jwks_url, cache_keys=True)


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate Supabase JWT token."""
    jwks_client = get_jwks_client()
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    options = {"verify_aud": False}
    try:
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=[signing_key.algorithm],
            audience=None,
            options=options,
        )
        return decoded
    except jwt.PyJWTError as exc:
        raise Auth.exceptions.HTTPException(
            status_code=401, detail=f"Invalid token: {exc}"
        ) from exc


@auth.authenticate
async def authenticate(authorization: str | None) -> str:
    """
    Authenticate requests using Supabase JWT tokens.
    
    Args:
        authorization: Bearer token from Authorization header
        
    Returns:
        user_id: The user ID from the token's 'sub' claim
        
    Raises:
        HTTPException: If token is missing or invalid
    """
    if not authorization:
        raise Auth.exceptions.HTTPException(
            status_code=401, detail="Missing authorization header"
        )
    
    # Extract token from "Bearer <token>" format
    if not authorization.startswith("Bearer "):
        raise Auth.exceptions.HTTPException(
            status_code=401, detail="Invalid authorization format"
        )
    
    token = authorization.split(" ", 1)[1].strip()
    
    # Decode and validate token
    claims = decode_token(token)
    
    # Extract user ID from token
    user_id = claims.get("sub")
    if not user_id:
        raise Auth.exceptions.HTTPException(
            status_code=401, detail="Token missing subject"
        )
    
    return str(user_id)


@auth.on
async def authorize_default(ctx: Auth.types.AuthContext, value: dict[str, Any]) -> bool:
    """
    Default authorization: allow all authenticated users.
    
    This allows any authenticated user to access all resources.
    You can customize this to add more restrictive authorization rules.
    """
    # Allow all authenticated requests
    # The authenticate decorator ensures only valid tokens pass through
    return True

