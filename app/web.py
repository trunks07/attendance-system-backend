from fastapi import Depends, FastAPI
from fastapi.middleware.gzip import GZipMiddleware

# Routers
from app.http.controllers import (
    SystemController,
    UserController,
)
from app.services.AuthService import verify_token


def routing(app: FastAPI):
    # Default Routings
    app.include_router(SystemController.router)

    app.include_router(UserController.router, prefix="/users")

    app.add_middleware(GZipMiddleware)

    return app
