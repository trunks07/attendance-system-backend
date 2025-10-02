from datetime import datetime, timedelta, timezone
from typing import Annotated, Final, cast
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from pydantic import BaseModel
from app.config.credentials import Hash
from app.config.database import get_db
from app.models.schemas.UserSchema import User
from app.models.User import UserModel

# Ensure SECRET_KEY and ALGORITHM are non-None for mypy and runtime safety
if Hash.key is None:
    raise RuntimeError("SECRET_KEY (Hash.key) is not configured")
if Hash.algorithm is None:
    raise RuntimeError("ALGORITHM (Hash.algorithm) is not configured")

SECRET_KEY: Final[str] = cast(str, Hash.key)
ALGORITHM: Final[str] = cast(str, Hash.algorithm)
ACCESS_TOKEN_EXPIRE_MINUTES: Final[int] = cast(int, Hash.access_token_expire_minutes)


class TokenData(BaseModel):
    email: str


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


async def get_user(email: str):
    db = await get_db()
    user_model = UserModel(db)
    return await user_model.get_by_email(email)


async def authenticate_user(email: str, password: str):
    user = await get_user(email)
    if not user:
        return False
    if not verify_password(password, user["password"]):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    # SECRET_KEY and ALGORITHM are typed as str (non-None) above
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: Annotated[str, Depends(oauth2_scheme)]) -> TokenData:
    """
    Decode and validate JWT. Returns TokenData or raises HTTPException.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise credentials_exception
        return TokenData(email=email)
    except InvalidTokenError:
        raise credentials_exception


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    token_data = verify_token(token)
    user_dict = await get_user(email=token_data.email)
    if not user_dict:
        raise HTTPException(status_code=401, detail="User not found")
    user = User(**user_dict)
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if not current_user:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
