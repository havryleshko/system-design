from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status


class JWKSClient:
    def __init__(self, jwks_url: str) -> None:
        self.jwks_url = jwks_url

    @lru_cache(maxsize=1)
    def get_jwks(self) -> Dict[str, Any]:
        try:
            response = httpx.get(self.jwks_url, timeout=10)
            response.raise_for_status()
        except Exception as exc:  # pragma: no cover - network failure
            raise RuntimeError(f"Failed to fetch JWKS: {exc}") from exc
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("JWKS payload malformed")
        return data

    def get_signing_key(self, token: str) -> jwt.api_jws.PyJWK:
        jwks_client = jwt.PyJWKClient(self.jwks_url, cache_keys=True)
        return jwks_client.get_signing_key_from_jwt(token)


def get_jwks_client() -> JWKSClient:
    jwks_url = os.getenv("SUPABASE_JWKS_URL")
    if not jwks_url:
        raise RuntimeError("SUPABASE_JWKS_URL not configured")
    return JWKSClient(jwks_url)


def decode_token(token: str, jwks_client: JWKSClient) -> Dict[str, Any]:
    signing_key = jwks_client.get_signing_key(token)
    options = {"verify_aud": False}
    try:
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=[signing_key.algorithm],
            audience=None,
            options=options,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    return decoded


def get_current_user(request: Request, jwks_client: JWKSClient = Depends(get_jwks_client)) -> Dict[str, Any]:
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = auth_header.split(" ", 1)[1].strip()
    claims = decode_token(token, jwks_client)
    request.state.token_claims = claims
    return claims


def require_user_id(claims: Dict[str, Any] = Depends(get_current_user)) -> str:
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject")
    return str(sub)


