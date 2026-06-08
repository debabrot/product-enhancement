from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.enrich import router as enrich_router
from app.core.logging import logger
from app.core.tracing import setup_tracing
from app.dependencies import get_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs ON STARTUP
    logger.info("Application startup complete. Ready to handle requests.")
    yield
    # This runs ON SHUTDOWN
    logger.info("Application shutting down...")


def create_app() -> FastAPI:
    logger.info("Initializing Product Enhancement API...")

    # Pass the lifespan context manager to FastAPI
    app = FastAPI(
        title="Product Enhancement API",
        version="0.1.0",
        description="Agentic product enrichment pipeline",
        lifespan=lifespan,
    )

    # Set up config
    config = get_config()
    setup_tracing(app, config.service_name, config.jaeger_endpoint)

    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(enrich_router)
    logger.info("Enrich router successfully included.")

    @app.get("/health")
    async def health(): return {"status": "ok"}
    
    return app


app = create_app()

