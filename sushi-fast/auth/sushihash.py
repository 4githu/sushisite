import os
import bcrypt

PEPPER = os.getenv("Pepper", "")
MAX_BCRYPT_BYTES = 72


class PasswordTooLongError(ValueError):
    """Raised when the password and server pepper cannot be hashed by bcrypt."""


def _password_bytes(password):
    if not isinstance(password, str):
        raise ValueError("비밀번호 형식이 올바르지 않습니다.")

    value = (password + PEPPER).encode("utf-8")
    if len(value) > MAX_BCRYPT_BYTES:
        raise PasswordTooLongError("비밀번호가 너무 깁니다. 64자 이내로 다시 설정해주세요.")
    return value

def make_hash(password):
    password = _password_bytes(password)

    salt = bcrypt.gensalt()

    hashed = bcrypt.hashpw(password, salt)

    return hashed.decode()

def check_hash(password, hashed):
    password = _password_bytes(password)
    hashed = hashed.encode()

    return bcrypt.checkpw(password, hashed)
