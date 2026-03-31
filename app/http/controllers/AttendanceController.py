from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from app.config.database import get_db
from app.libs.helper import Helper
from app.models.Attendance import AttendanceCreate, AttendanceModel, AttendanceUpdate
from app.models.schemas.AttendanceSchema import Attendance
from app.services.MemberClassificationService import MemberClassificationService

router = APIRouter(tags=["Attendance"])


@router.get("/", response_model=list[Attendance])
async def index(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(
        None, description="Search term for Email or full_name"
    ),
    tribe: Optional[str] = Query(None, description="Tribe ID"),
    start_datetime: Optional[str] = Query(None, description="Start datetime"),
    end_datetime: Optional[str] = Query(None, description="End datetime"),
):
    db = await get_db()

    # Calculate skip value
    skip = (page - 1) * page_size

    # Get paginated results with optional search
    attendances, total_count = await AttendanceModel(db).get_attendance_list(
        skip=skip,
        limit=page_size,
        search_term=search,
        tribe=tribe,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
    )

    response = Helper.paginate(
        data=attendances,
        total_count=total_count,
        skip=skip,
        page=page,
        page_size=page_size,
        search=search,
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK, content=jsonable_encoder(response)
    )


@router.post("/", response_model=Attendance)
async def store(request: AttendanceCreate, background_tasks: BackgroundTasks):
    try:
        db = await get_db()
        result = await AttendanceModel(db).create(request)

        background_tasks.add_task(
            MemberClassificationService().checkMemberClassification,
            member_id=result["member_id"],
            type=result["type"],
        )

        return JSONResponse(
            status_code=status.HTTP_201_CREATED, content=jsonable_encoder(result)
        )
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})


@router.get("/{attendance_id}", response_model=Attendance)
async def show(attendance_id: str):
    try:
        db = await get_db()
        result = await AttendanceModel(db).get_by_id(attendance_id)

        if not result:
            raise HTTPException(status_code=404, detail="Item not found")

        return JSONResponse(
            status_code=status.HTTP_200_OK, content=jsonable_encoder(result)
        )
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})


@router.put("/{attendance_id}", response_model=Attendance)
async def update(attendance_id: str, request: AttendanceUpdate):
    try:
        db = await get_db()

        if not await AttendanceModel(db).get_by_id(attendance_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Attendance not found"
            )

        result = await AttendanceModel(db).update(attendance_id, request)

        return JSONResponse(
            status_code=status.HTTP_200_OK, content=jsonable_encoder(result)
        )
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})


@router.delete("/{attendance_id}", response_model=None)
async def delete(attendance_id: str):
    try:
        db = await get_db()

        if not await AttendanceModel(db).get_by_id(attendance_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Attendance not found"
            )

        await AttendanceModel(db).delete(attendance_id)

        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content={})
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})
