import uuid

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import (
    analysis,
    captions,
    connections,
    demo,
    draft,
    glossaries,
    health,
    internal,
    jobs,
    localizations,
    onboarding,
    projects,
    publishes,
    schedules,
    thumbnails,
    transcripts,
    uploads,
    users,
    ws,
)
from app.auth.read_only import (
    READ_ONLY_MESSAGE,
    is_read_only_allowed,
    is_write_method,
    write_token_claims,
)
from app.config import get_settings
from app.errors import AppError, error_body

_HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
}


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Creator Helper Studio API",
        version="0.1.0",
        docs_url="/docs" if settings.is_local else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.is_local else None,
    )

    # Registered before CORS so CORS wraps it: a read-only 403 then still carries the CORS
    # headers the browser needs to surface the error. (Starlette wraps last-added outermost,
    # so the middleware defined first here ends up innermost.)
    @app.middleware("http")
    async def read_only_middleware(request: Request, call_next):
        """Reject writes from demo accounts before any router or service runs.

        This is the enforcement, not a hint: the UI disables the same controls, but a crafted
        request is stopped here. Non-read-only deployments (`read_only_user_uids` empty) pay
        nothing. Requests without a valid token fall through so the router returns its own 401.
        """
        if (
            settings.read_only_user_uids
            and is_write_method(request.method)
            and not is_read_only_allowed(request.url.path)
        ):
            header = request.headers.get("authorization", "")
            if header.lower().startswith("bearer "):
                claims = await run_in_threadpool(write_token_claims, header[7:].strip())
                if claims is not None:
                    # Cache the verified claims so `current_user` need not verify again.
                    request.state.firebase_token_claims = claims
                if claims is not None and claims.get("uid") in settings.read_only_user_uids:
                    return JSONResponse(
                        status_code=403,
                        content=error_body(
                            code="FORBIDDEN",
                            message=READ_ONLY_MESSAGE,
                            request_id=_request_id(request),
                            details={"reason": "read_only_demo"},
                        ),
                    )
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-request-id"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        # Every response here is authenticated, per-user, and changes on each write.
        # An intermediary that caches one serves another user's data or, far more
        # likely, a stale error: Firebase Hosting's CDN cached a 404 from
        # `/transcript` for ten minutes and hid a transcript that already existed.
        # Say no-store at the origin so no layer in front can second-guess it.
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        vary = response.headers.get("Vary", "")
        response.headers["Vary"] = f"{vary}, Authorization" if vary else "Authorization"
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(
                code=exc.code,
                message=exc.message,
                request_id=_request_id(request),
                details=exc.details,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code=code, message=message, request_id=_request_id(request)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=error_body(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                request_id=_request_id(request),
                details={"errors": jsonable_encoder(exc.errors())},
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=error_body(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred.",
                request_id=_request_id(request),
            ),
        )

    app.include_router(health.router, prefix="/api")
    app.include_router(demo.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(onboarding.router, prefix="/api")
    app.include_router(connections.router, prefix="/api")
    app.include_router(projects.router, prefix="/api")
    app.include_router(uploads.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(ws.router, prefix="/api")
    app.include_router(transcripts.router, prefix="/api")
    app.include_router(captions.router, prefix="/api")
    app.include_router(thumbnails.router, prefix="/api")
    app.include_router(draft.router, prefix="/api")
    app.include_router(localizations.router, prefix="/api")
    app.include_router(glossaries.router, prefix="/api")
    app.include_router(analysis.router, prefix="/api")
    app.include_router(publishes.router, prefix="/api")
    app.include_router(schedules.router, prefix="/api")
    app.include_router(internal.router, prefix="/api")
    return app


app = create_app()
