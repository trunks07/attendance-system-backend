from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from app.config.database import get_db
from app.libs.helper import Helper
from app.models.schemas.TribeSchema import Tribe
from app.models.Tribe import TribeCreate, TribeModel, TribeUpdate

router = APIRouter(tags=["Tribe"])


@router.get("/", response_model=list[Tribe])
async def index(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(
        None, description="Search term for Email or full_name"
    ),
):
    try:
        db = await get_db()

        # Calculate skip value
        skip = (page - 1) * page_size

        # Get paginated results with optional search
        tribes, total_count = await TribeModel(db).get_tribe_list(
            skip=skip, limit=page_size, search_term=search
        )

        response = Helper.paginate(
            data=tribes,
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


@router.post("/", response_model=Tribe)
async def store(request: TribeCreate):
    try:
        db = await get_db()
        result = await TribeModel(db).create(request)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED, content=jsonable_encoder(result)
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(e)}
        )


@router.get("/{tribe_id}", response_model=Tribe)
async def show(tribe_id: str):
    try:
        db = await get_db()
        result = await TribeModel(db).get_by_id(tribe_id)

        return JSONResponse(
            status_code=status.HTTP_200_OK, content=jsonable_encoder(result)
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(e)}
        )


@router.put("/{tribe_id}", response_model=Tribe)
async def update(tribe_id: str, request: TribeUpdate):
    try:
        db = await get_db()
        tribe_model = TribeModel(db)

        if not await tribe_model.get_by_id(tribe_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Tribe not found"
            )

        result = await tribe_model.update(tribe_id, request)

        return JSONResponse(
            status_code=status.HTTP_200_OK, content=jsonable_encoder(result)
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(e)}
        )


@router.delete("/{tribe_id}", response_model=None)
async def delete(tribe_id: str):
    try:
        db = await get_db()

        if not await TribeModel(db).get_by_id(tribe_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Tribe not found"
            )

        await TribeModel(db).delete(tribe_id)

        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content={})
    except HTTPException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(e)}
        )
