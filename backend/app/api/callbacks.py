"""
Callbacks from the Channel Stub.
The stub calls POST /callbacks/delivery as each message changes state.
The stub calls POST /callbacks/reply when a customer replies.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.models.models import (
    CampaignMessage, CustomerReply, Campaign,
    MessageStatus, CampaignStatus, ReplyType
)
import uuid

router = APIRouter(prefix="/callbacks", tags=["callbacks"])


def make_id():
    return str(uuid.uuid4())


class DeliveryCallback(BaseModel):
    message_id: str
    status: str  # delivered / failed / opened / clicked / purchased
    timestamp: Optional[str] = None


class ReplyCallback(BaseModel):
    message_id: str
    customer_id: str
    campaign_id: str
    message: str
    reply_type: str = "simple"  # simple / sensitive / unsubscribe


STATUS_TRANSITIONS = {
    "delivered": MessageStatus.delivered,
    "failed": MessageStatus.failed,
    "opened": MessageStatus.opened,
    "clicked": MessageStatus.clicked,
    "purchased": MessageStatus.purchased,
}


@router.post("/delivery")
def handle_delivery_callback(payload: DeliveryCallback, db: Session = Depends(get_db)):
    msg = db.query(CampaignMessage).filter(CampaignMessage.id == payload.message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    new_status = STATUS_TRANSITIONS.get(payload.status)
    if not new_status:
        raise HTTPException(status_code=400, detail=f"Unknown status: {payload.status}")

    now = datetime.utcnow()

    # Update message status — only advance, never go backwards
    status_order = ["pending", "sent", "delivered", "opened", "clicked", "purchased", "failed"]
    current_idx = status_order.index(msg.status.value) if msg.status.value in status_order else 0
    new_idx = status_order.index(payload.status) if payload.status in status_order else 0

    if new_idx > current_idx or payload.status == "failed":
        msg.status = new_status

        if payload.status == "delivered":
            msg.delivered_at = now
        elif payload.status == "opened":
            msg.opened_at = now
        elif payload.status == "clicked":
            msg.clicked_at = now
        elif payload.status == "purchased":
            msg.purchased_at = now
        elif payload.status == "failed":
            msg.failed_at = now

        db.commit()

    # Check if campaign is fully resolved
    _check_campaign_completion(msg.campaign_id, db)

    return {"ok": True, "message_id": payload.message_id, "status": payload.status}


@router.post("/reply")
def handle_reply_callback(payload: ReplyCallback, db: Session = Depends(get_db)):
    reply_type = ReplyType(payload.reply_type) if payload.reply_type in [r.value for r in ReplyType] else ReplyType.simple

    auto_response = None
    auto_responded = False
    flagged = False

    if reply_type == ReplyType.unsubscribe:
        auto_response = "You've been unsubscribed. You won't receive marketing messages from us anymore. Reply START to re-subscribe anytime."
        auto_responded = True
    elif reply_type == ReplyType.simple:
        auto_response = "Thanks for reaching out! Our team will get back to you soon. ☕"
        auto_responded = True
    elif reply_type == ReplyType.sensitive:
        flagged = True

    reply = CustomerReply(
        id=make_id(),
        customer_id=payload.customer_id,
        campaign_id=payload.campaign_id,
        message=payload.message,
        reply_type=reply_type,
        auto_responded=auto_responded,
        auto_response_text=auto_response,
        flagged_to_marketer=flagged,
    )
    db.add(reply)
    db.commit()

    return {
        "ok": True,
        "reply_id": reply.id,
        "auto_responded": auto_responded,
        "flagged": flagged,
    }


def _check_campaign_completion(campaign_id: str, db: Session):
    """Mark campaign completed when no more pending/sent messages remain"""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign or campaign.status == CampaignStatus.completed:
        return

    remaining = db.query(CampaignMessage).filter(
        CampaignMessage.campaign_id == campaign_id,
        CampaignMessage.status.in_([MessageStatus.pending, MessageStatus.sent])
    ).count()

    if remaining == 0:
        campaign.status = CampaignStatus.completed
        campaign.completed_at = datetime.utcnow()
        db.commit()
