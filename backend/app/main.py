from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import customers, campaigns, callbacks, opportunities, segments, replies
from app.core.database import engine
from app.models.models import Base

# Create tables on startup (idempotent)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ShopPulse CRM",
    description="AI-native CRM engine for consumer brands",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(customers.router)
app.include_router(campaigns.router)
app.include_router(callbacks.router)
app.include_router(opportunities.router)
app.include_router(segments.router)
app.include_router(replies.router)


@app.get("/")
def root():
    return {"service": "xeno-crm-backend", "status": "ok", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/seed")
def seed_data():
    """Trigger seed script — idempotent"""
    from app.core.seed import run_seed
    run_seed()
    return {"ok": True, "message": "Seed completed"}
