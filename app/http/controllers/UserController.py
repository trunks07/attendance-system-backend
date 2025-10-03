from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from app.config.database import get_db
from app.http.requests.ChangeUserPasswordRequest import ChangeUserPasswordRequest
from app.http.requests.CreateUserRequest import CreateUserRequest
from app.libs.helper import Helper
from app.models.schemas.UserSchema import User
from app.models.User import UserCreate, UserModel, UserUpdate
from app.services.AuthService import get_password_hash

router = APIRouter(tags=["User"])


@router.get("/", response_model=list[User])
async def index(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term for Email or full_name"),
):
    try:
        db = await get_db()

        # Calculate skip value
        skip = (page - 1) * page_size

        # Get paginated results with optional search
        users, total_count = await UserModel(db).get_user_list(
            skip=skip, limit=page_size, search_term=search
        )

        response = Helper.paginate(
            data=users,
            total_count=total_count,
            skip=skip,
            page=page,
            page_size=page_size,
            search=search,
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK, content=jsonable_encoder(response)
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(e)}
        )


@router.post("/", response_model=User)
async def store(request: CreateUserRequest):
    try:
        db = await get_db()
        user_model = UserModel(db)

        payload = request.model_dump()
        payload["password"] = get_password_hash(payload["password"])

        existing = await UserModel(db).get_by_email(payload["email"])

        if existing:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"message": "Email already exists"},
            )

        user_data = UserCreate(**payload)
        user = await user_model.create(user_data)

        return JSONResponse(
            status_code=status.HTTP_200_OK, content=jsonable_encoder(user)
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(e)}
        )


@router.get("/{user_id}", response_model=User)
async def show(user_id: str):
    try:
        db = await get_db()
        user = await UserModel(db).get_by_id(user_id)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return JSONResponse(
            status_code=status.HTTP_200_OK, content=jsonable_encoder(user)
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(e)}
        )


@router.put("/{user_id}", response_model=User)
async def update(user_id: str, request: UserUpdate):
    try:
        db = await get_db()
        user_model = UserModel(db)

        user = await user_model.get_by_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        response = await user_model.update(user_id, request)

        return JSONResponse(
            status_code=status.HTTP_200_OK, content=jsonable_encoder(response)
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(e)}
        )


@router.patch("/{user_id}", response_model=None)
async def update_password(user_id: str, request: ChangeUserPasswordRequest):
    try:
        payload = request.model_dump()

        db = await get_db()
        user_model = UserModel(db)

        user = await user_model.get_by_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        await user_model.update_password(
            user["_id"], get_password_hash(payload["password"])
        )

        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content={})
    except HTTPException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(e)}
        )


@router.delete("/{user_id}", response_model=None)
async def delete(user_id: str):
    try:
        db = await get_db()
        user_model = UserModel(db)

        user = await user_model.get_by_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        await user_model.delete(user_id)

        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content={})
    except HTTPException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(e)}
        )
