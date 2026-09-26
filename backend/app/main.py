"""Chitro FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.adapters import ChannelAdapterError
from app.ai.provider import AIProviderError
from app.api.campaigns import router as campaigns_router
from app.api.posts import router as posts_router
from app.database import init_db
from app.domain.exceptions import InvalidStateTransitionError, ResourceNotFoundError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Execute startup and shutdown events."""
    await init_db()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Chitro API",
        description="AI Content Operations Studio / Multi-Platform Command Center",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception Handlers
    @app.exception_handler(ResourceNotFoundError)
    async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc), "resource_type": exc.resource_type, "identifier": exc.identifier},
        )

    @app.exception_handler(InvalidStateTransitionError)
    async def invalid_transition_handler(request: Request, exc: InvalidStateTransitionError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": str(exc),
                "current_status": exc.current.value,
                "target_status": exc.target.value,
            },
        )

    @app.exception_handler(AIProviderError)
    async def ai_provider_error_handler(request: Request, exc: AIProviderError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "AI generation provider encountered an error", "error": str(exc)},
        )

    @app.exception_handler(ChannelAdapterError)
    async def channel_adapter_error_handler(request: Request, exc: ChannelAdapterError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "Publishing channel adapter error", "error": str(exc), "provider": exc.provider},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )

    # Mount API routers
    app.include_router(campaigns_router, prefix="/api")
    app.include_router(posts_router, prefix="/api")

    @app.get("/health", tags=["System"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "app": "chitro"}

    return app


app = create_app()
