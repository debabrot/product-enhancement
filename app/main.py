import structlog
from fastapi import FastAPI

from app.api.enrich import router as enrich_router


def create_app() -> FastAPI:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
    )

    app = FastAPI(title="Product Enhancement API")
    app.include_router(enrich_router)
    return app


app = create_app()
