from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import logger
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Digital Commerce Intelligence Platform...")
    logger.info(
        f"Environment: {settings.ENVIRONMENT} | API Host: {settings.API_HOST}:{settings.API_PORT}"
    )

    # Ensure tables exist for dev/test SQLite
    if settings.DATABASE_URL.startswith("sqlite"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("SQLite database schemas verified.")

    yield
    logger.info("Shutting down Digital Commerce Intelligence Platform...")
    await engine.dispose()


app = FastAPI(
    title="Système de surveillance du commerce numérique",
    description="Plateforme de collecte contrôlée de pages Facebook, de conservation des éléments justificatifs et d’extraction déterministe des signaux commerciaux.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_router)

# Mount Static Assets & Dashboard
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_dashboard():
        return FileResponse(static_dir / "index.html")


# Mount Mock Facebook Pages for testing and local Playwright evaluation
mock_dir = Path("/app/MOCK/hackthone-ESB-moch-fcb-pages-for-agents-")
if not mock_dir.exists():
    mock_dir = (
        Path(__file__).resolve().parent.parent.parent
        / "MOCK"
        / "hackthone-ESB-moch-fcb-pages-for-agents-"
    )

if mock_dir.exists():
    app.mount("/mock", StaticFiles(directory=str(mock_dir), html=True), name="mock")
