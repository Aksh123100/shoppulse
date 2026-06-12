from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional
from datetime import datetime
import uuid
import httpx

from app.core.database import get_db
from app.core.config import settings
from app.models.models import (
    Campaign, CampaignMessage, Customer, CampaignMemory,
    CampaignStatus, MessageStatus, Channel
)
from pydantic import BaseModel

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


class CampaignCreate(BaseModel):
    name: str
    opportunity_type: str
    segment_criteria: dict
    estimated_revenue: float = 0.0
    ai_reasoning: Optional[str] = None


class MessageDraft(BaseModel):
    customer_id: str
    channel: str
    message_text: str
    scheduled_at: Optional[datetime] = None
    channel_confidence: str = "low"
    channel_reasoning: Optional[str] = None


class CampaignCreateFull(BaseModel):
    name: str
    opportunity_type: str
    segment_criteria: dict
    estimated_revenue: float = 0.0
    ai_reasoning: Optional[str] = None
    messages: list[MessageDraft]
    scheduled_at: Optional[datetime] = None


def make_id():
    return str(uuid.uuid4())


@router.get("")
def list_campaigns(
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(Campaign)
    if status:
        q = q.filter(Campaign.status == status)
    campaigns = q.order_by(desc(Campaign.created_at)).all()

    result = []
    for c in campaigns:
        # Aggregate message stats
        total = db.query(CampaignMessage).filter(CampaignMessage.campaign_id == c.id).count()
        sent = db.query(CampaignMessage).filter(
            CampaignMessage.campaign_id == c.id,
            CampaignMessage.status.in_([
                MessageStatus.sent, MessageStatus.delivered, MessageStatus.opened,
                MessageStatus.clicked, MessageStatus.purchased, MessageStatus.failed
            ])
        ).count()
        opened = db.query(CampaignMessage).filter(
            CampaignMessage.campaign_id == c.id,
            CampaignMessage.status.in_([
                MessageStatus.opened, MessageStatus.clicked, MessageStatus.purchased
            ])
        ).count()
        purchased = db.query(CampaignMessage).filter(
            CampaignMessage.campaign_id == c.id,
            CampaignMessage.status == MessageStatus.purchased
        ).count()

        result.append({
            "id": c.id,
            "name": c.name,
            "opportunity_type": c.opportunity_type,
            "status": c.status.value,
            "total_customers": c.total_customers,
            "estimated_revenue": c.estimated_revenue,
            "scheduled_at": c.scheduled_at,
            "sent_at": c.sent_at,
            "created_at": c.created_at,
            "stats": {
                "total": total,
                "sent": sent,
                "opened": opened,
                "purchased": purchased,
                "open_rate": round(opened / sent, 2) if sent > 0 else 0,
            }
        })

    return result


@router.post("")
def create_campaign(payload: CampaignCreateFull, db: Session = Depends(get_db)):
    campaign_id = make_id()

    campaign = Campaign(
        id=campaign_id,
        name=payload.name,
        opportunity_type=payload.opportunity_type,
        segment_criteria=payload.segment_criteria,
        estimated_revenue=payload.estimated_revenue,
        ai_reasoning=payload.ai_reasoning,
        total_customers=len(payload.messages),
        status=CampaignStatus.draft,
        scheduled_at=payload.scheduled_at,
    )
    db.add(campaign)
    db.flush()

    messages = []
    for m in payload.messages:
        msg = CampaignMessage(
            id=make_id(),
            campaign_id=campaign_id,
            customer_id=m.customer_id,
            channel=Channel(m.channel),
            message_text=m.message_text,
            scheduled_at=m.scheduled_at,
            status=MessageStatus.pending,
            channel_confidence=m.channel_confidence,
            channel_reasoning=m.channel_reasoning,
        )
        messages.append(msg)

    db.add_all(messages)
    db.commit()

    return {"id": campaign_id, "status": "draft", "total_customers": len(messages)}


@router.get("/{campaign_id}")
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    messages = db.query(CampaignMessage).filter(
        CampaignMessage.campaign_id == campaign_id
    ).all()

    status_counts = {}
    for msg in messages:
        s = msg.status.value
        status_counts[s] = status_counts.get(s, 0) + 1

    memory = campaign.memory

    return {
        "id": campaign.id,
        "name": campaign.name,
        "opportunity_type": campaign.opportunity_type,
        "segment_criteria": campaign.segment_criteria,
        "status": campaign.status.value,
        "total_customers": campaign.total_customers,
        "estimated_revenue": campaign.estimated_revenue,
        "ai_reasoning": campaign.ai_reasoning,
        "scheduled_at": campaign.scheduled_at,
        "sent_at": campaign.sent_at,
        "completed_at": campaign.completed_at,
        "created_at": campaign.created_at,
        "stats": status_counts,
        "memory": {
            "open_rate": memory.open_rate,
            "click_rate": memory.click_rate,
            "conversion_rate": memory.conversion_rate,
            "revenue_recovered": memory.revenue_recovered,
            "learnings": memory.learnings,
        } if memory else None,
    }


@router.get("/{campaign_id}/live")
def get_campaign_live(campaign_id: str, db: Session = Depends(get_db)):
    """Real-time stats — called by Watching Agent and Live Monitor"""
    messages = db.query(CampaignMessage).filter(
        CampaignMessage.campaign_id == campaign_id
    ).all()

    total = len(messages)
    status_counts = {s.value: 0 for s in MessageStatus}
    for msg in messages:
        status_counts[msg.status.value] += 1

    delivered = (status_counts["delivered"] + status_counts["opened"] +
                 status_counts["clicked"] + status_counts["purchased"])
    opened = status_counts["opened"] + status_counts["clicked"] + status_counts["purchased"]
    clicked = status_counts["clicked"] + status_counts["purchased"]
    purchased = status_counts["purchased"]
    sent = status_counts["sent"] + delivered + status_counts["failed"]

    return {
        "campaign_id": campaign_id,
        "total": total,
        "pending": status_counts["pending"],
        "sent": sent,
        "delivered": delivered,
        "failed": status_counts["failed"],
        "opened": opened,
        "clicked": clicked,
        "purchased": purchased,
        "delivery_rate": round(delivered / sent, 3) if sent > 0 else 0,
        "open_rate": round(opened / delivered, 3) if delivered > 0 else 0,
        "click_rate": round(clicked / opened, 3) if opened > 0 else 0,
        "conversion_rate": round(purchased / clicked, 3) if clicked > 0 else 0,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/{campaign_id}/send")
async def send_campaign(
    campaign_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Fire campaign — sends all pending messages to channel stub"""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status not in [CampaignStatus.draft, CampaignStatus.scheduled]:
        raise HTTPException(status_code=400, detail=f"Campaign is {campaign.status.value}, cannot send")

    messages = db.query(CampaignMessage).filter(
        CampaignMessage.campaign_id == campaign_id,
        CampaignMessage.status == MessageStatus.pending,
    ).all()

    if not messages:
        raise HTTPException(status_code=400, detail="No pending messages to send")

    # Update campaign status
    campaign.status = CampaignStatus.live
    campaign.sent_at = datetime.utcnow()
    db.commit()

    # Fire messages to channel stub in background
    background_tasks.add_task(_dispatch_to_channel_stub, campaign_id, [m.id for m in messages])

    return {
        "status": "sending",
        "campaign_id": campaign_id,
        "messages_dispatched": len(messages),
    }


async def _dispatch_to_channel_stub(campaign_id: str, message_ids: list[str]):
    """Background task: pull message details and POST to channel stub"""
    db = SessionLocal_import()
    try:
        for msg_id in message_ids:
            msg = db.query(CampaignMessage).filter(CampaignMessage.id == msg_id).first()
            if not msg:
                continue

            customer = db.query(Customer).filter(Customer.id == msg.customer_id).first()

            payload = {
                "message_id": msg.id,
                "campaign_id": campaign_id,
                "customer_id": msg.customer_id,
                "phone": customer.phone if customer else "unknown",
                "channel": msg.channel.value,
                "message_text": msg.message_text,
                "callback_url": f"{settings.CRM_CALLBACK_URL}/callbacks/delivery",
                "reply_callback_url": f"{settings.CRM_CALLBACK_URL}/callbacks/reply",
            }

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(f"{settings.CHANNEL_STUB_URL}/send", json=payload)

                msg.status = MessageStatus.sent
                msg.sent_at = datetime.utcnow()
                db.commit()
            except Exception as e:
                msg.status = MessageStatus.failed
                msg.failed_at = datetime.utcnow()
                db.commit()
                print(f"Failed to dispatch message {msg_id}: {e}")
    finally:
        db.close()


def SessionLocal_import():
    from app.core.database import SessionLocal
    return SessionLocal()
