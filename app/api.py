from fastapi import FastAPI, Depends
from fastapi.middleware.gzip import GZipMiddleware
from app.services.AuthService import verify_token

# Routers
from app.http.controllers import (
    SystemController,
    UserController,
    AuthController
)

def routing(app: FastAPI):
    # Default Routings
    app.include_router(SystemController.router)

    app.include_router(UserController.router, prefix="/users", dependencies=[Depends(verify_token)])
    app.include_router(AuthController.router, prefix="/auth")

    app.add_middleware(GZipMiddleware)

    return app
