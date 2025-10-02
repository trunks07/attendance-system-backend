from datetime import timedelta
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from app.config.database import get_db
from app.libs.helper import Helper
from app.models.schemas.UserSchema import User
from app.services.AuthService import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    use_refresh_token,
    get_current_active_user
)
from app.models.User import UserModel
from app.config.credentials import Hash
from app.http.requests.LoginRequest import LoginRequest
from app.http.requests.RefreshTokenRequest import RefreshTokenRequest
from app.http.requests.ChangeUserPasswordRequest import ChangeUserPasswordRequest


router = APIRouter(tags=["Auth"])

@router.post("/login")
async def login(request: LoginRequest):
    try:
        db = await get_db()
        user_model = UserModel(db)
        payload = request.model_dump()

        user = await user_model.get_by_email(payload["email"])

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        if not verify_password(payload["password"], user["password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )

        access_token_expires = timedelta(minutes=Hash.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user["_id"]}, expires_delta=access_token_expires
        )

        refresh_token_expires = timedelta(minutes=Hash.refresh_token_expire_minutes)
        refresh_toke = create_refresh_token(
            data={"sub": user["_id"]}, expires_delta=refresh_token_expires
        )

        response = {
            "user": {
                "email": user["email"],
                "full_name": user["full_name"],
            },
            "token": {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": access_token_expires.total_seconds(),
            },
            "refresh_token": {
                "refresh_token": refresh_toke,
                "token_type": "bearer",
                "expires_in": refresh_token_expires.total_seconds(),
            }
        }

        return JSONResponse(
            status_code=status.HTTP_200_OK, content=jsonable_encoder(response)
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(e)}
        )

@router.post("/refresh")
async def refresh_token(request: RefreshTokenRequest):
    try:
        payload = request.model_dump()
        response = use_refresh_token(payload['refresh_token'])

        return JSONResponse(
            status_code=status.HTTP_200_OK, content=jsonable_encoder(response)
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(e)}
        )

@router.get("/profile", response_model=User)
async def get_profile(profile: Annotated[User, Depends(get_current_active_user)]):
    try:
        return JSONResponse(
            status_code=status.HTTP_200_OK, content=jsonable_encoder(profile)
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(e)}
        )

@router.patch("/change-password", response_model=User)
async def change_password(
    profile: Annotated[User, Depends(get_current_active_user)],
    request: ChangeUserPasswordRequest
):
    try:
        payload = request.model_dump()

        db = await get_db()
        user_model = UserModel(db)

        await user_model.update_password(profile["_id"], get_password_hash(payload["password"]))
        return JSONResponse(
            status_code=status.HTTP_204_NO_CONTENT, content={}
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(e)}
        )
