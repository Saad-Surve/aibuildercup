import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import health
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Creator Helper Studio API",
        version="0.1.0",
        docs_url="/docs" if settings.is_local else None,
        redoc_url=None,
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred.",
                    "requestId": getattr(request.state, "request_id", None),
                    "details": {},
                }
            },
        )

    app.include_router(health.router)
    return app


app = create_app()
