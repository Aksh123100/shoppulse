from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel

from app.core.database import get_db
from app.models.models import CustomerReply, Customer

router = APIRouter(prefix="/replies", tags=["replies"])


class RespondPayload(BaseModel):
    response_text: str


@router.get("/flagged")
def get_flagged_replies(db: Session = Depends(get_db)):
    replies = db.query(CustomerReply).filter(
        CustomerReply.flagged_to_marketer == True
    ).order_by(desc(CustomerReply.created_at)).all()

    result = []
    for r in replies:
        customer = db.query(Customer).filter(Customer.id == r.customer_id).first()
        result.append({
            "id": r.id,
            "customer_id": r.customer_id,
            "customer_name": customer.name if customer else "Unknown",
            "campaign_id": r.campaign_id,
            "message": r.message,
            "reply_type": r.reply_type.value,
            "flagged": r.flagged_to_marketer,
            "created_at": r.created_at.isoformat(),
        })

    return result


@router.post("/{reply_id}/respond")
def respond_to_reply(reply_id: str, payload: RespondPayload, db: Session = Depends(get_db)):
    reply = db.query(CustomerReply).filter(CustomerReply.id == reply_id).first()
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")

    reply.auto_response_text = payload.response_text
    reply.auto_responded = True
    reply.flagged_to_marketer = False
    db.commit()

    return {"ok": True, "reply_id": reply_id}
