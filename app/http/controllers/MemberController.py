from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from app.config.database import get_db
from app.http.requests.CreateMemberRequest import CreateMemberRequest
from app.http.requests.UpdateMemberRequest import UpdateMemberRequest
from app.libs.helper import Helper
from app.models.Lifegroup import LifegroupModel
from app.models.Member import MemberCreate, MemberModel, MemberUpdate
from app.models.schemas.LifegroupSchema import LifegroupUpdate
from app.models.schemas.MemberSchema import Member

router = APIRouter(tags=["Member"])


@router.get("/", response_model=list[Member])
async def index(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(
        None,
        description="Search term for First Name, Last Name, Middle Name and Address",
    ),
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
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})


@router.post("/", response_model=Member)
async def store(request: CreateMemberRequest):
    try:
        db = await get_db()
        payload = request.model_dump()
        result = await MemberModel(db).create(MemberCreate(**payload))

        if payload["lifegroup_id"]:
            lifegroup = await LifegroupModel(db).get_by_id(payload["lifegroup_id"])

            if not lifegroup:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Lifegroup not found"
                )

            # Set the members of the LG
            existing_members = lifegroup["members"]
            members = [*existing_members, result["_id"]]

            await LifegroupModel(db).update(
                payload["lifegroup_id"], LifegroupUpdate(**{"members": members})
            )

        return JSONResponse(
            status_code=status.HTTP_201_CREATED, content=jsonable_encoder(result)
        )
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})


@router.get("/{member_id}", response_model=Member)
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
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})


@router.put("/{member_id}", response_model=Member)
async def update(member_id: str, request: UpdateMemberRequest):
    try:
        db = await get_db()
        payload = request.model_dump()

        existing_data = await MemberModel(db).get_by_id(member_id)
        if not existing_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
            )

        result = await MemberModel(db).update(member_id, MemberUpdate(**payload))

        if payload["lifegroup_id"]:
            lifegroup = await LifegroupModel(db).get_by_id(payload["lifegroup_id"])

            if not lifegroup:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Lifegroup not found"
                )

            # Reset the member lists of the old lifegroup
            old_lg = await LifegroupModel(db).get_lifegroup_by_member_id(
                existing_data["_id"]
            )
            if old_lg:
                existing_members = old_lg["members"]
                old_lg_members = [
                    member
                    for member in existing_members
                    if member != existing_data["_id"]
                ]
                await LifegroupModel(db).update(
                    old_lg["_id"], LifegroupUpdate(**{"members": old_lg_members})
                )

            # Set the members of the member's new lifegroup
            existing_members = lifegroup["members"]
            members = [*existing_members, result["_id"]]

            await LifegroupModel(db).update(
                payload["lifegroup_id"], LifegroupUpdate(**{"members": members})
            )

        return JSONResponse(
            status_code=status.HTTP_200_OK, content=jsonable_encoder(result)
        )
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})


@router.delete("/{member_id}", response_model=None)
async def delete(member_id: str):
    try:
        db = await get_db()
        existing_data = await MemberModel(db).get_by_id(member_id)

        if not existing_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
            )

        # Reset the member lists of the old lifegroup
        old_lg = await LifegroupModel(db).get_lifegroup_by_member_id(
            existing_data["_id"]
        )
        if old_lg:
            existing_members = old_lg["members"]
            old_lg_members = [
                member for member in existing_members if member != existing_data["_id"]
            ]
            await LifegroupModel(db).update(
                old_lg["_id"], LifegroupUpdate(**{"members": old_lg_members})
            )

        await MemberModel(db).delete(member_id)

        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content={})
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})
