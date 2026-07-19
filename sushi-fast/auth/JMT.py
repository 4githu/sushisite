from jose import jwt
import json
from jose import JWTError
from datetime import datetime, timedelta, timezone
from fastapi import Request
from fastapi import HTTPException
import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

def make_jwt(sub, data, index):
    data = dict(data)

    payload = {k: data[k] for k in index if k in data}

    return jwt.encode(
        {
            "sub": str(sub),
            "data": payload,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def check_jwt(request: Request, key: str):
    if not SECRET_KEY:
        raise HTTPException(status_code=500, detail="JWT_SECRET_KEY가 설정되지 않았습니다.")

    token = request.cookies.get(key)

    if not token:
        raise HTTPException(status_code=401, detail="Token not found")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")