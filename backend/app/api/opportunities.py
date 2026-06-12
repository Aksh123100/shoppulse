"""
Opportunities API — surfaces pre-scanned revenue opportunities.
In the full product, this is populated by the Thinking Agent on a schedule.
For now, we compute it on-the-fly from customer data so it always reflects
current state. The AI agent will enrich these with reasoning text.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.models import Customer, Order, LifecycleStage

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


@router.get("")
def get_opportunities(db: Session = Depends(get_db)):
    """
    Returns 2-3 ranked revenue opportunities.
    Each opportunity has: title, urgency, rupee value at stake, segment size, rationale.
    """
    opportunities = []

    # Opportunity 1: High-value at-risk customers
    at_risk = db.query(Customer).filter(
        Customer.lifecycle_stage == LifecycleStage.at_risk,
        Customer.total_spend >= 500,
    ).all()

    if at_risk:
        revenue_at_risk = sum(c.total_spend * 0.3 for c in at_risk)  # 30% of their spend = potential reactivation
        avg_days_since = 0
        for c in at_risk:
            if c.last_purchase_date:
                avg_days_since += (datetime.utcnow() - c.last_purchase_date).days
        avg_days_since = avg_days_since // len(at_risk) if at_risk else 0

        # Urgency: if avg 60+ days, window is closing
        urgency = "critical" if avg_days_since >= 65 else ("high" if avg_days_since >= 50 else "medium")

        opportunities.append({
            "id": "opp-at-risk-high-value",
            "title": "High-value customers going silent",
            "subtitle": f"{len(at_risk)} shoppers who spent ₹500+ haven't returned in {avg_days_since} days on average",
            "urgency": urgency,
            "revenue_at_stake": round(revenue_at_risk),
            "customer_count": len(at_risk),
            "opportunity_type": "lapsed",
            "segment_criteria": {
                "lifecycle_stage": "at_risk",
                "min_spend": 500,
            },
            "window_note": "Re-engagement window closes ~90 days. Act before they hit churn.",
            "cta": "Win them back",
        })

    # Opportunity 2: Loyal customers primed for upsell
    loyal = db.query(Customer).filter(
        Customer.lifecycle_stage == LifecycleStage.loyal,
        Customer.order_count >= 6,
    ).all()

    if loyal:
        # Subscription upsell potential
        potential_upsell = sum(
            2100 for c in loyal if c.total_spend < 5000  # haven't subscribed yet
        )

        opportunities.append({
            "id": "opp-loyal-upsell",
            "title": "Loyal customers ready for subscription",
            "subtitle": f"{len(loyal)} regulars ordering 6+ times — a subscription offer lands hardest now",
            "urgency": "high",
            "revenue_at_stake": round(potential_upsell * 0.33),  # 33% conversion estimate
            "customer_count": len(loyal),
            "opportunity_type": "primed",
            "segment_criteria": {
                "lifecycle_stage": "loyal",
                "min_orders": 6,
            },
            "window_note": "Best time to convert repeat buyers is between order 6 and 10.",
            "cta": "Pitch the subscription",
        })

    # Opportunity 3: Growing customers about to lapse
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    growing_lapsing = db.query(Customer).filter(
        Customer.lifecycle_stage == LifecycleStage.growing,
        Customer.last_purchase_date <= thirty_days_ago,
    ).all()

    if growing_lapsing:
        revenue_at_stake = sum(c.total_spend * 0.4 for c in growing_lapsing)

        opportunities.append({
            "id": "opp-growing-lapsing",
            "title": "Growing customers losing momentum",
            "subtitle": f"{len(growing_lapsing)} customers who were on a good streak haven't ordered in 30+ days",
            "urgency": "medium",
            "revenue_at_stake": round(revenue_at_stake * 0.25),
            "customer_count": len(growing_lapsing),
            "opportunity_type": "lapsed",
            "segment_criteria": {
                "lifecycle_stage": "growing",
                "days_since_purchase": 30,
            },
            "window_note": "Catch them before they slip to at-risk. Easier to re-engage at this stage.",
            "cta": "Nudge them back",
        })

    # Sort by revenue at stake
    opportunities.sort(key=lambda x: x["revenue_at_stake"], reverse=True)

    # Summary stats for top of page
    total_customers = db.query(Customer).count()
    total_revenue_at_stake = sum(o["revenue_at_stake"] for o in opportunities)

    return {
        "opportunities": opportunities,
        "total_revenue_at_stake": round(total_revenue_at_stake),
        "total_customers": total_customers,
        "last_scanned": datetime.utcnow().isoformat(),
    }
