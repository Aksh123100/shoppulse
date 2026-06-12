from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.models.models import Customer, LifecycleStage

router = APIRouter(prefix="/segments", tags=["segments"])


class SegmentPreviewRequest(BaseModel):
    lifecycle_stage: Optional[str] = None
    min_spend: Optional[float] = None
    max_spend: Optional[float] = None
    min_orders: Optional[int] = None
    days_since_purchase: Optional[int] = None
    channel: Optional[str] = None


@router.post("/preview")
def preview_segment(payload: SegmentPreviewRequest, db: Session = Depends(get_db)):
    """Preview how many customers match criteria before building campaign"""
    q = db.query(Customer)

    if payload.lifecycle_stage:
        q = q.filter(Customer.lifecycle_stage == payload.lifecycle_stage)
    if payload.min_spend is not None:
        q = q.filter(Customer.total_spend >= payload.min_spend)
    if payload.max_spend is not None:
        q = q.filter(Customer.total_spend <= payload.max_spend)
    if payload.min_orders is not None:
        q = q.filter(Customer.order_count >= payload.min_orders)
    if payload.days_since_purchase is not None:
        cutoff = datetime.utcnow() - timedelta(days=payload.days_since_purchase)
        q = q.filter(Customer.last_purchase_date <= cutoff)
    if payload.channel:
        q = q.filter(Customer.channel_preference == payload.channel)

    customers = q.all()
    total = len(customers)

    # Revenue stats for the segment
    total_spend = sum(c.total_spend for c in customers)
    avg_spend = total_spend / total if total > 0 else 0

    stage_breakdown = {}
    for c in customers:
        s = c.lifecycle_stage.value
        stage_breakdown[s] = stage_breakdown.get(s, 0) + 1

    channel_breakdown = {}
    for c in customers:
        ch = c.channel_preference.value
        channel_breakdown[ch] = channel_breakdown.get(ch, 0) + 1

    return {
        "total": total,
        "total_spend": round(total_spend, 2),
        "avg_spend": round(avg_spend, 2),
        "stage_breakdown": stage_breakdown,
        "channel_breakdown": channel_breakdown,
        "sample_customers": [
            {
                "id": c.id,
                "name": c.name,
                "total_spend": c.total_spend,
                "order_count": c.order_count,
                "lifecycle_stage": c.lifecycle_stage.value,
                "channel_preference": c.channel_preference.value,
                "last_purchase_date": c.last_purchase_date.isoformat() if c.last_purchase_date else None,
            }
            for c in customers[:10]
        ],
    }


@router.get("/{criteria_hash}/customers")
def get_segment_customers(criteria_hash: str, db: Session = Depends(get_db)):
    """Placeholder — in production, segments are persisted. For now, return all."""
    customers = db.query(Customer).limit(100).all()
    return [{"id": c.id, "name": c.name} for c in customers]
