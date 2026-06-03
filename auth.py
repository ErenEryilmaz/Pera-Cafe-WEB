import os
import time
import secrets
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "admin123")

TOKEN_TTL = 3600 * 8   # 8 saat

# Basit in-memory token store (production'da Redis kullanın)
active_tokens: dict[str, float] = {}   # token → expiry timestamp

security = HTTPBearer()


def verify_token(cred: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = cred.credentials
    exp = active_tokens.get(token)
    if not exp or time.time() > exp:
        active_tokens.pop(token, None)
        raise HTTPException(401, "Geçersiz veya süresi dolmuş token.")
    return token


def create_admin_token(username: str, password: str) -> str:
    if username != ADMIN_USER or password != ADMIN_PASS:
        raise HTTPException(401, "Kullanıcı adı veya şifre hatalı.")
    token = secrets.token_hex(32)
    active_tokens[token] = time.time() + TOKEN_TTL
    return token


def revoke_token(token: str):
    active_tokens.pop(token, None)
