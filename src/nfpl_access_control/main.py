"""ASGI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nfpl_access_control import __version__
from nfpl_access_control.api.routers import admin, authorization, health, identity, jobs
from nfpl_access_control.core.config import settings


def create_app(*, cors_allowed_origins: tuple[str, ...] | None = None) -> FastAPI:
    application = FastAPI(
        title="NFPL Access Control Service",
        version=__version__,
        description="Authentication and authorization for NFPL shipment jobs.",
    )
    allowed_origins = (
        settings.cors_allowed_origins if cors_allowed_origins is None else cors_allowed_origins
    )
    if allowed_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(allowed_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "If-Match"],
        )
    application.include_router(health.router)
    application.include_router(identity.router, prefix="/v1")
    application.include_router(authorization.router, prefix="/v1")
    application.include_router(admin.router, prefix="/v1")
    application.include_router(jobs.router, prefix="/v1")
    return application


app = create_app()
