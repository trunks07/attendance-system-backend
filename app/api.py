from fastapi import Depends, FastAPI
from fastapi.middleware.gzip import GZipMiddleware

# Routers
from app.http.controllers import AuthController, SystemController, UserController
from app.services.AuthService import verify_token


def routing(app: FastAPI):
    # Default Routings
    app.include_router(SystemController.router)

    app.include_router(
        UserController.router, prefix="/users", dependencies=[Depends(verify_token)]
    )
    app.include_router(AuthController.router, prefix="/auth")

    app.add_middleware(GZipMiddleware)

    return app
