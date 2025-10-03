from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from app.config.database import get_db
from app.libs.helper import Helper
from app.models.schemas.MemberSchema import Member
from app.models.Member import MemberCreate, MemberModel, MemberUpdate

router = APIRouter(tags=["Member"])

@router.get('/', response_model=list[Member])
async def index(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(
        None, description="Search term for First Name, Last Name, Middle Name and Address"
    )
):
    try:
        db = await get_db()

        # Calculate skip value
        skip = (page - 1) * page_size

        # Get paginated results with optional search
        members, total_count = await MemberModel(db).get_member_list(
            skip=skip, limit=page_size, search_term=search
        )

        response = Helper.paginate(
            data=members,
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

@router.post('/', response_model=Member)
async def store(request: MemberCreate):
    try:
        db = await get_db()
        result = await MemberModel(db).create(request)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED, content=jsonable_encoder(result)
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(e)}
        )

@router.get('/{member_id}', response_model=Member)
async def show(member_id: str):
    try:
        db = await get_db()
        result = await MemberModel(db).get_member_full_details(member_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
            )

        return JSONResponse(
            status_code=status.HTTP_200_OK, content=jsonable_encoder(result)
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(e)}
        )

@router.put('/{member_id}', response_model=Member)
async def update(member_id: str, request: MemberUpdate):
    try:
        db = await get_db()

        if not await MemberModel(db).get_by_id(member_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
            )

        result = await MemberModel(db).update(member_id, request)

        return JSONResponse(
            status_code=status.HTTP_200_OK, content=jsonable_encoder(result)
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(e)}
        )

@router.delete('/{member_id}', response_model=None)
async def delete(member_id: str):
    try:
        db = await get_db()

        if not await MemberModel(db).get_by_id(member_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
            )

        await MemberModel(db).delete(member_id)

        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content={})
    except HTTPException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(e)}
        )