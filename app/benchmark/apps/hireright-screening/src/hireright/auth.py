"""OIDC bearer-token authentication (Keycloak realm `hr`) and role checks."""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from .settings import settings

oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.auth_issuer}/protocol/openid-connect/token")


@dataclass
class Principal:
    id: str
    roles: set[str]


def get_current_recruiter(token: str = Depends(oauth2)) -> Principal:
    try:
        claims = jwt.decode(token, settings.jwks_key, algorithms=["RS256"], audience=settings.auth_audience)
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "invalid token") from exc
    roles = set(claims.get("realm_access", {}).get("roles", []))
    if "recruiter" not in roles and "screening-admin" not in roles:
        raise HTTPException(403, "recruiter role required")
    return Principal(id=claims["sub"], roles=roles)


def require_role(role: str):
    def dep(p: Principal = Depends(get_current_recruiter)) -> Principal:
        if role not in p.roles:
            raise HTTPException(403, f"{role} role required")
        return p
    return dep
