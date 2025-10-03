from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from app.config.database import get_db
from app.libs.helper import Helper
from app.models.schemas.LifegroupSchema import Lifegroup
from app.models.Lifegroup import LifegroupCreate, LifegroupModel, LifegroupUpdate

router = APIRouter(tags=["Lifegroup"])

@router.get('/', response_model=list[Lifegroup])
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
        lifegroups, total_count = await LifegroupModel(db).get_lifegroup_list(
            skip=skip, limit=page_size, search_term=search
        )

        response = Helper.paginate(
            data=lifegroups,
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
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})

@router.post('/', response_model=Lifegroup)
async def store(request: LifegroupCreate):
    try:
        db = await get_db()
        result = await LifegroupModel(db).create(request)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED, content=jsonable_encoder(result)
        )
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})

@router.get('/{lifegroup_id}', response_model=Lifegroup)
async def show(lifegroup_id: str):
    try:
        db = await get_db()
        result = await LifegroupModel(db).get_full_details(lifegroup_id)

        if not result:
            raise HTTPException(status_code=404, detail="Item not found")

        return JSONResponse(
            status_code=status.HTTP_200_OK, content=jsonable_encoder(result)
        )
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})

@router.put('/{lifegroup_id}', response_model=Lifegroup)
async def update(lifegroup_id: str, request: LifegroupUpdate):
    try:
        db = await get_db()

        if not await LifegroupModel(db).get_by_id(lifegroup_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Lifegroup not found"
            )

        result = await LifegroupModel(db).update(lifegroup_id, request)

        return JSONResponse(
            status_code=status.HTTP_200_OK, content=jsonable_encoder(result)
        )
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})

@router.delete('/{lifegroup_id}', response_model=None)
async def delete(lifegroup_id: str):
    try:
        db = await get_db()

        if not await LifegroupModel(db).get_by_id(lifegroup_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Lifegroup not found"
            )

        await LifegroupModel(db).delete(lifegroup_id)

        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content={})
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})