from fastapi import Depends, FastAPI
from fastapi.middleware.gzip import GZipMiddleware

# Routers
from app.http.controllers import (
    AuthController,
    SystemController,
    TribeController,
    UserController,
)
from app.services.AuthService import verify_token


def routing(app: FastAPI):
    # Default Routings
    app.include_router(SystemController.router)
    app.include_router(AuthController.router, prefix="/auth")

    app.include_router(
        UserController.router, prefix="/users", dependencies=[Depends(verify_token)]
    )

    app.include_router(
        TribeController.router, prefix="/tribes", dependencies=[Depends(verify_token)]
    )

    app.add_middleware(GZipMiddleware)

    return app
