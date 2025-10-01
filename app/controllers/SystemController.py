from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.get("/")
async def index():
    try:
        return {
            "status": status.HTTP_200_OK,
            "message": "Welcome to Attendance System Backend",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"System un-healthy! Error: {str(e)}",
        )


# System health check
@router.get("/healthz")
async def healthCheck():
    try:
        return {"status": status.HTTP_200_OK, "message": "System is healthy!"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"System un-healthy! Error: {str(e)}",
        )
