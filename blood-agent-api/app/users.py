from typing import Optional
from pydantic import BaseModel
from passlib.context import CryptContext

# Use pbkdf2_sha256 to avoid bcrypt's 72-byte password limit in environments
# where passwords may be long. Keep a small fallback truncation just in case.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class User(BaseModel):
    username: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = False


class UserInDB(User):
    hashed_password: str


# Simple in-memory user store for demo purposes
_users_db: dict[str, UserInDB] = {}


def get_user(username: str) -> Optional[UserInDB]:
    return _users_db.get(username)


def create_user(username: str, password: str, full_name: str | None = None) -> User:
    try:
        hashed = pwd_context.hash(password)
    except ValueError:
        # As a last-resort fallback, truncate to 72 bytes and hash
        hashed = pwd_context.hash(password[:72])
    user = UserInDB(username=username, full_name=full_name, disabled=False, hashed_password=hashed)
    _users_db[username] = user
    return User(username=username, full_name=full_name)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
