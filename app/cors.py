from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware


def cors_settings(app: FastAPI):
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app
