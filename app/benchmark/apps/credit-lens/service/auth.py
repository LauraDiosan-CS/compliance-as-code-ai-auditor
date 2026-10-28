"""OAuth2 client-credentials tokens issued by the ACME identity provider (machine-to-machine)."""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .settings import settings

bearer = HTTPBearer()


@dataclass
class Principal:
    client_id: str
    scopes: set[str]


def verify_token(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> Principal:
    try:
        claims = jwt.decode(cred.credentials, settings.idp_public_key, algorithms=["RS256"], audience="creditlens")
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "invalid token") from exc
    scopes = set(claims.get("scope", "").split())
    if "creditlens:score" not in scopes:
        raise HTTPException(403, "missing scope")
    return Principal(client_id=claims["client_id"], scopes=scopes)


def require_scope(scope: str):
    def dep(p: Principal = Depends(verify_token)) -> Principal:
        if scope not in p.scopes:
            raise HTTPException(403, f"missing scope {scope}")
        return p
    return dep
