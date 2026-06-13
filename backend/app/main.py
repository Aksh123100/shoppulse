from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import customers, campaigns, callbacks, opportunities, segments, replies
from app.api.agent import router as agent_router
from app.api.watching_agent import start_watching_agent, stop_watching_agent
from app.core.database import engine
from app.models.models import Base

# Create tables on startup (same as Day 1 — idempotent)
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP: start the 4 background jobs
    start_watching_agent()
    yield
    # SHUTDOWN: stop the scheduler cleanly
    stop_watching_agent()


app = FastAPI(
    title="ShopPulse CRM",
    description="AI-native CRM engine for consumer brands",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── All Day 1 routers — unchanged ──
app.include_router(customers.router)
app.include_router(campaigns.router)
app.include_router(callbacks.router)
app.include_router(opportunities.router)
app.include_router(segments.router)
app.include_router(replies.router)

# ── Day 2 addition ──
app.include_router(agent_router)


@app.get("/")
def root():
    return {"service": "shoppulse-backend", "status": "ok", "version": "2.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy", "version": "2.0.0"}


@app.post("/seed")
def seed_data():
    """Trigger seed script — idempotent"""
    from app.core.seed import run_seed
    run_seed()
    return {"ok": True, "message": "Seed completed"}
