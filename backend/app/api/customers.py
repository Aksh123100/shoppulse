from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Optional
from app.core.database import get_db
from app.models.models import Customer, Order, LifecycleStage, Channel
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/customers", tags=["customers"])


class CustomerOut(BaseModel):
    id: str
    name: str
    phone: str
    email: Optional[str]
    channel_preference: str
    total_spend: float
    order_count: int
    last_purchase_date: Optional[datetime]
    lifecycle_stage: str
    health_score: int
    created_at: datetime

    class Config:
        from_attributes = True


class CustomerDetail(CustomerOut):
    orders: list[dict]


@router.get("", response_model=dict)
def list_customers(
    lifecycle_stage: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    min_spend: Optional[float] = Query(None),
    max_spend: Optional[float] = Query(None),
    min_orders: Optional[int] = Query(None),
    days_since_purchase: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Customer)

    if lifecycle_stage:
        q = q.filter(Customer.lifecycle_stage == lifecycle_stage)
    if channel:
        q = q.filter(Customer.channel_preference == channel)
    if min_spend is not None:
        q = q.filter(Customer.total_spend >= min_spend)
    if max_spend is not None:
        q = q.filter(Customer.total_spend <= max_spend)
    if min_orders is not None:
        q = q.filter(Customer.order_count >= min_orders)
    if days_since_purchase is not None:
        cutoff = datetime.utcnow().__class__.utcnow() if False else \
            __import__("datetime").datetime.utcnow() - __import__("datetime").timedelta(days=days_since_purchase)
        q = q.filter(Customer.last_purchase_date <= cutoff)
    if search:
        q = q.filter(
            Customer.name.ilike(f"%{search}%") |
            Customer.phone.ilike(f"%{search}%") |
            Customer.email.ilike(f"%{search}%")
        )

    total = q.count()
    customers = q.order_by(desc(Customer.total_spend)).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "customers": [CustomerOut.model_validate(c) for c in customers],
    }


@router.get("/stats")
def customer_stats(db: Session = Depends(get_db)):
    """Aggregate stats for the dashboard header"""
    total = db.query(Customer).count()
    total_revenue = db.query(func.sum(Customer.total_spend)).scalar() or 0

    stage_breakdown = {}
    for stage in LifecycleStage:
        count = db.query(Customer).filter(Customer.lifecycle_stage == stage).count()
        stage_breakdown[stage.value] = count

    return {
        "total_customers": total,
        "total_revenue": round(total_revenue, 2),
        "stage_breakdown": stage_breakdown,
    }


@router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: str, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Customer not found")

    orders_data = [
        {
            "id": o.id,
            "product_name": o.product_name,
            "amount": o.amount,
            "purchased_at": o.purchased_at.isoformat(),
        }
        for o in sorted(customer.orders, key=lambda x: x.purchased_at, reverse=True)
    ]

    result = CustomerDetail.model_validate(customer)
    result.orders = orders_data
    return result


@router.get("/{customer_id}/channel-profile")
def get_channel_profile(customer_id: str, db: Session = Depends(get_db)):
    """
    Returns per-customer channel intelligence.
    Analyzes their past campaign message history to determine optimal channel + timing.
    """
    from app.models.models import CampaignMessage, MessageStatus
    from collections import defaultdict

    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Customer not found")

    # Fetch their message history
    msgs = db.query(CampaignMessage).filter(
        CampaignMessage.customer_id == customer_id,
        CampaignMessage.status.in_([
            MessageStatus.delivered, MessageStatus.opened,
            MessageStatus.clicked, MessageStatus.purchased
        ])
    ).all()

    data_points = len(msgs)

    if data_points == 0:
        return {
            "customer_id": customer_id,
            "recommended_channel": customer.channel_preference.value,
            "recommended_timing": "Tuesday 10AM",
            "confidence": "low",
            "reason": "No engagement history yet — using customer preference + industry benchmark",
            "data_points": 0,
        }

    # Compute per-channel open rates
    channel_stats = defaultdict(lambda: {"sent": 0, "opened": 0})
    for msg in msgs:
        channel_stats[msg.channel.value]["sent"] += 1
        if msg.status in [MessageStatus.opened, MessageStatus.clicked, MessageStatus.purchased]:
            channel_stats[msg.channel.value]["opened"] += 1

    best_channel = customer.channel_preference.value
    best_rate = 0.0
    for ch, stats in channel_stats.items():
        if stats["sent"] > 0:
            rate = stats["opened"] / stats["sent"]
            if rate > best_rate:
                best_rate = rate
                best_channel = ch

    confidence = "low" if data_points < 5 else ("medium" if data_points < 10 else "high")

    return {
        "customer_id": customer_id,
        "recommended_channel": best_channel,
        "recommended_timing": "Tuesday 10AM",  # Simplified — real logic in AI agent
        "open_rate": round(best_rate, 2),
        "confidence": confidence,
        "reason": f"Based on {data_points} past interactions",
        "data_points": data_points,
    }
