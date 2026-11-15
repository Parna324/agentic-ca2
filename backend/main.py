"""FastAPI application entry point for the Code Review Board."""
import logging
import logging.config
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models.database import init_db
from api.routes import router
from core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Code Review Board backend...")
    init_db()
    logger.info(f"Database initialized. Offline mode: {settings.offline_mode}")
    yield
    logger.info("Shutting down...")

app = FastAPI(
    title="Code Review Board API",
    description="AI-Powered Multi-Agent Pull Request Review System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Code Review Board API", "docs": "/docs", "version": "1.0.0"}
