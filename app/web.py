from fastapi import Depends, FastAPI
from fastapi.middleware.gzip import GZipMiddleware

# Routers
from app.controllers import (
    SystemController,
)
from app.services.AuthService import verify_token


def routing(app: FastAPI):
    # Default Routings
    app.include_router(SystemController.router)

    app.add_middleware(GZipMiddleware)

    return app
