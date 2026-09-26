from fastapi import APIRouter

from app.api.routes import (
    crawl_jobs,
    evidence,
    fiscal_registry,
    health,
    metrics,
    pages,
    posts,
    review_queue,
    targets,
)

api_router = APIRouter()

# Health check directly at root and /api/v1
api_router.include_router(health.router)

# Domain routes under /api/v1
v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(health.router)
v1_router.include_router(targets.router)
v1_router.include_router(crawl_jobs.router)
v1_router.include_router(pages.router)
v1_router.include_router(posts.router)
v1_router.include_router(evidence.router)
v1_router.include_router(review_queue.router)
v1_router.include_router(metrics.router)
v1_router.include_router(fiscal_registry.router)

# Direct un-prefixed routes for MVP API specification:
api_router.include_router(targets.router)
api_router.include_router(crawl_jobs.router)
api_router.include_router(pages.router)
api_router.include_router(posts.router)
api_router.include_router(evidence.router)
api_router.include_router(review_queue.router)
api_router.include_router(metrics.router)
api_router.include_router(fiscal_registry.router)

api_router.include_router(v1_router)
