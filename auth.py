import os
from datetime import datetime, timedelta

import jwt
import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = os.environ.get("JWT_SECRET", "xiaonuan-cbt-secret-key-2026-please-change-in-production")
ALGORITHM = "HS256"
EXPIRE_HOURS = 24 * 7  # 7 天有效

security = HTTPBearer()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_token(user_id: int, username: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.utcnow() + timedelta(hours=EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """JWT 认证依赖，返回当前用户信息"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        username = payload.get("username")
        if not user_id or not username:
            raise HTTPException(401, "无效的 token")
        return {"user_id": user_id, "username": username}
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "token 已过期，请重新登录")
    except jwt.PyJWTError:
        raise HTTPException(401, "无效的 token")
