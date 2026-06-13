"""
agent.py — Thinking Agent (ReAct pattern) — Groq version
Groq uses OpenAI-compatible API — same SDK, just different base_url and model.
No extra SDK needed beyond: pip install openai
Get free key at: console.groq.com (no credit card)
"""

import json
import os
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from datetime import datetime, timedelta
from openai import OpenAI
from dotenv import load_dotenv

from app.core.database import get_db
from app.models.models import (
    Customer, Order, Campaign, CampaignMessage,
    CampaignMemory, LifecycleStage, MessageStatus, Channel, CampaignStatus
)

load_dotenv()

router = APIRouter(prefix="/agent", tags=["agent"])

# ─────────────────────────────────────────────
# GROQ CLIENT — OpenAI SDK, different base_url
# This is the only difference from a standard OpenAI setup
# ─────────────────────────────────────────────
client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY", ""),
    base_url="https://api.groq.com/openai/v1"
)

GROQ_MODEL = "openai/gpt-oss-120b"


# ─────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    conversation_history: list = []

class CreateCampaignRequest(BaseModel):
    segment_criteria: dict
    message_template: str
    campaign_name: str
    channel: str = "whatsapp"
    opportunity_type: str = "custom"


# ─────────────────────────────────────────────
# TOOLS — OpenAI format
# Groq uses the exact same tool format as OpenAI
# Much simpler than Gemini's protos format
# ─────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_customers",
            "description": (
                "Fetch customers from the database with optional filters. "
                "Use this to understand who is in a segment before building a campaign. "
                "Returns count, sample customers, and aggregate stats."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "lifecycle_stage": {
                        "type": "string",
                        "description": "Filter by lifecycle stage: new, growing, loyal, at_risk, churned"
                    },
                    "min_health_score": {"type": "number", "description": "Minimum health score (0-100)"},
                    "max_health_score": {"type": "number", "description": "Maximum health score (0-100)"},
                    "days_since_purchase": {"type": "integer", "description": "Customers inactive for this many days"},
                    "min_spend": {"type": "number", "description": "Minimum total lifetime spend in rupees"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_profile",
            "description": "Get detailed profile for one customer: orders, channel history, health score.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "Customer UUID"}
                },
                "required": ["customer_id"]
            }
        }
    },
    {
    "type": "function",
    "function": {
        "name": "get_campaign_history",
        "description": (
            "Get past completed campaigns and their learnings. "
            "Always call this before recommending a new campaign to avoid repeating mistakes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "segment_type": {"type": "string", "description": "Filter: lapsed, primed, retry, custom"}
            }
        }
    }
},

    {
        "type": "function",
        "function": {
            "name": "calculate_revenue_at_risk",
            "description": "Calculate the rupee value at stake for a customer segment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lifecycle_stage": {"type": "string", "description": "at_risk, churned, new, growing, or loyal"},
                    "days_since_purchase": {"type": "integer", "description": "Only count customers inactive this many days"}
                },
                "required": ["lifecycle_stage"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_channel_profile",
            "description": "Get optimal channel and timing for one customer based on engagement history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "Customer UUID"}
                },
                "required": ["customer_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_segment",
            "description": "Build a segment from filter criteria. Returns size and customer IDs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lifecycle_stage": {"type": "string"},
                    "min_spend": {"type": "number"},
                    "days_since_purchase": {"type": "integer"},
                    "min_health_score": {"type": "number"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_campaign",
            "description": (
                "Create and save a campaign in the database. "
                "Use ONLY after confirming segment and message with marketer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "lifecycle_stage": {"type": "string"},
                    "message_template": {"type": "string", "description": "Message with {name}, {days} placeholders"},
                    "channel": {"type": "string", "description": "whatsapp or sms"},
                    "opportunity_type": {"type": "string", "description": "lapsed, primed, retry, or custom"},
                    "ai_reasoning": {"type": "string"}
                },
                "required": ["name", "message_template", "channel", "opportunity_type", "ai_reasoning"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_campaign_stats",
            "description": "Get live stats for a campaign: sent, delivered, opened, clicked, purchased rates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Campaign UUID"}
                },
                "required": ["campaign_id"]
            }
        }
    }
]


# ─────────────────────────────────────────────
# TOOL EXECUTION FUNCTIONS — unchanged from before
# ─────────────────────────────────────────────

def execute_get_customers(params: dict, db: Session) -> dict:
    query = db.query(Customer)
    if "lifecycle_stage" in params:
        query = query.filter(Customer.lifecycle_stage == params["lifecycle_stage"])
    if "min_health_score" in params:
        query = query.filter(Customer.health_score >= params["min_health_score"])
    if "max_health_score" in params:
        query = query.filter(Customer.health_score <= params["max_health_score"])
    if "min_spend" in params:
        query = query.filter(Customer.total_spend >= params["min_spend"])
    if "days_since_purchase" in params:
        cutoff = datetime.utcnow() - timedelta(days=params["days_since_purchase"])
        query = query.filter(Customer.last_purchase_date <= cutoff)
    limit = int(params.get("limit", 20))
    total_count = query.count()
    customers = query.limit(limit).all()
    total_spend = sum(c.total_spend or 0 for c in customers)
    avg_health = sum(c.health_score or 0 for c in customers) / max(len(customers), 1)
    return {
        "total_count": total_count,
        "returned_sample": len(customers),
        "aggregate": {
            "total_spend_rupees": round(total_spend, 2),
            "avg_health_score": round(avg_health, 1),
        },
        "customers": [
            {
                "id": c.id,
                "name": c.name,
                "lifecycle_stage": c.lifecycle_stage.value if hasattr(c.lifecycle_stage, 'value') else c.lifecycle_stage,
                "health_score": c.health_score,
                "total_spend": c.total_spend,
                "last_purchase_date": c.last_purchase_date.isoformat() if c.last_purchase_date else None,
                "channel_preference": c.channel_preference.value if hasattr(c.channel_preference, 'value') else c.channel_preference,
            }
            for c in customers
        ]
    }


def execute_get_customer_profile(params: dict, db: Session) -> dict:
    customer = db.query(Customer).filter(Customer.id == str(params["customer_id"])).first()
    if not customer:
        return {"error": "Customer not found"}
    orders = db.query(Order).filter(Order.customer_id == customer.id)\
               .order_by(Order.purchased_at.desc()).limit(5).all()
    days_since = (datetime.utcnow() - customer.last_purchase_date).days if customer.last_purchase_date else None
    return {
        "id": customer.id, "name": customer.name, "phone": customer.phone,
        "channel_preference": customer.channel_preference.value if hasattr(customer.channel_preference, 'value') else customer.channel_preference,
        "lifecycle_stage": customer.lifecycle_stage.value if hasattr(customer.lifecycle_stage, 'value') else customer.lifecycle_stage,
        "health_score": customer.health_score, "total_spend": customer.total_spend,
        "order_count": customer.order_count,
        "last_purchase_date": customer.last_purchase_date.isoformat() if customer.last_purchase_date else None,
        "days_since_last_purchase": days_since,
        "recent_orders": [
            {"product": o.product_name, "amount": o.amount, "date": o.purchased_at.date().isoformat()}
            for o in orders
        ]
    }


def execute_get_campaign_history(params: dict, db: Session) -> dict:
    query = db.query(Campaign).filter(Campaign.status == CampaignStatus.completed)
    if "segment_type" in params:
        query = query.filter(Campaign.opportunity_type == params["segment_type"])
    limit = int(params.get("limit", 5))
    campaigns = query.order_by(Campaign.created_at.desc()).limit(limit).all()
    results = []
    for c in campaigns:
        memory = db.query(CampaignMemory).filter(CampaignMemory.campaign_id == c.id).first()
        results.append({
            "id": c.id, "name": c.name, "opportunity_type": c.opportunity_type,
            "total_customers": c.total_customers,
            "status": c.status.value if hasattr(c.status, 'value') else c.status,
            "learnings": memory.learnings if memory else None,
            "open_rate": memory.open_rate if memory else None,
            "click_rate": memory.click_rate if memory else None,
            "conversion_rate": memory.conversion_rate if memory else None,
            "revenue_recovered": memory.revenue_recovered if memory else None,
        })
    return {"campaigns": results, "total": len(results)}


def execute_calculate_revenue_at_risk(params: dict, db: Session) -> dict:
    query = db.query(Customer)
    stage = params.get("lifecycle_stage")
    if stage:
        query = query.filter(Customer.lifecycle_stage == stage)
    if "days_since_purchase" in params:
        cutoff = datetime.utcnow() - timedelta(days=params["days_since_purchase"])
        query = query.filter(Customer.last_purchase_date <= cutoff)
    customers = query.all()
    total_spend = sum(c.total_spend or 0 for c in customers)
    avg_spend = total_spend / max(len(customers), 1)
    recovery_potential = len(customers) * avg_spend * 0.30 * 0.50
    return {
        "segment": stage, "customer_count": len(customers),
        "total_historical_spend_rupees": round(total_spend, 2),
        "avg_spend_per_customer_rupees": round(avg_spend, 2),
        "estimated_recovery_potential_rupees": round(recovery_potential, 2),
        "reasoning": f"{len(customers)} customers, ₹{total_spend:,.0f} total spend. Recovery potential ₹{recovery_potential:,.0f}."
    }


def execute_get_channel_profile(params: dict, db: Session) -> dict:
    from collections import defaultdict
    customer = db.query(Customer).filter(Customer.id == str(params["customer_id"])).first()
    if not customer:
        return {"error": "Customer not found"}
    msgs = db.query(CampaignMessage)\
             .filter(CampaignMessage.customer_id == customer.id)\
             .filter(CampaignMessage.status.in_([
                 MessageStatus.delivered, MessageStatus.opened,
                 MessageStatus.clicked, MessageStatus.purchased
             ])).all()
    data_points = len(msgs)
    industry_defaults = {
        "whatsapp": {"time": "10:00", "day": "Tuesday", "open_rate": 0.48},
        "sms":      {"time": "19:00", "day": "Sunday",  "open_rate": 0.38}
    }
    preferred = customer.channel_preference.value if hasattr(customer.channel_preference, 'value') else customer.channel_preference
    if data_points == 0:
        return {
            "customer_id": customer.id, "customer_name": customer.name,
            "recommended_channel": preferred,
            "recommended_time": industry_defaults.get(preferred, industry_defaults["whatsapp"])["time"],
            "confidence": "low", "data_points": 0,
            "reasoning": "No engagement history. Using industry benchmark."
        }
    channel_stats = defaultdict(lambda: {"sent": 0, "opened": 0})
    for msg in msgs:
        ch = msg.channel.value if hasattr(msg.channel, 'value') else msg.channel
        channel_stats[ch]["sent"] += 1
        if msg.status in [MessageStatus.opened, MessageStatus.clicked, MessageStatus.purchased]:
            channel_stats[ch]["opened"] += 1
    best_channel = preferred
    best_rate = 0.0
    for ch, stats in channel_stats.items():
        if stats["sent"] > 0:
            rate = stats["opened"] / stats["sent"]
            if rate > best_rate:
                best_rate = rate
                best_channel = ch
    confidence = "low" if data_points < 5 else ("medium" if data_points < 10 else "high")
    return {
        "customer_id": customer.id, "customer_name": customer.name,
        "recommended_channel": best_channel,
        "recommended_time": industry_defaults.get(best_channel, industry_defaults["whatsapp"])["time"],
        "open_rate": round(best_rate, 2), "confidence": confidence,
        "data_points": data_points,
        "reasoning": f"Based on {data_points} past interactions."
    }


def execute_create_segment(params: dict, db: Session) -> dict:
    query = db.query(Customer)
    if "lifecycle_stage" in params:
        query = query.filter(Customer.lifecycle_stage == params["lifecycle_stage"])
    if "min_spend" in params:
        query = query.filter(Customer.total_spend >= params["min_spend"])
    if "min_health_score" in params:
        query = query.filter(Customer.health_score >= params["min_health_score"])
    if "max_health_score" in params:
        query = query.filter(Customer.health_score <= params["max_health_score"])
    if "days_since_purchase" in params:
        cutoff = datetime.utcnow() - timedelta(days=params["days_since_purchase"])
        query = query.filter(Customer.last_purchase_date <= cutoff)
    customers = query.all()
    total_spend = sum(c.total_spend or 0 for c in customers)
    return {
        "segment_size": len(customers), "criteria": params,
        "total_spend_rupees": round(total_spend, 2),
        "customer_ids": [c.id for c in customers[:500]],
        "summary": f"Segment of {len(customers)} customers with ₹{total_spend:,.0f} total spend"
    }


def execute_create_campaign(params: dict, db: Session) -> dict:
    criteria = {k: params[k] for k in ["lifecycle_stage", "min_spend", "days_since_purchase", "min_health_score"] if k in params}
    segment_result = execute_create_segment(criteria, db)
    customer_ids = segment_result["customer_ids"]
    if not customer_ids:
        return {"error": "No customers match the segment criteria"}
    campaign = Campaign(
        id=str(uuid.uuid4()), name=params["name"],
        opportunity_type=params["opportunity_type"],
        segment_criteria=criteria, total_customers=len(customer_ids),
        status=CampaignStatus.draft, ai_reasoning=params.get("ai_reasoning", ""),
        estimated_revenue=0.0, created_at=datetime.utcnow()
    )
    db.add(campaign)
    db.flush()
    template = params["message_template"]
    channel_str = params.get("channel", "whatsapp")
    customers = db.query(Customer).filter(Customer.id.in_(customer_ids)).all()
    for customer in customers:
        days_since = (datetime.utcnow() - customer.last_purchase_date).days if customer.last_purchase_date else "a while"
        first_name = customer.name.split()[0]
        personalized_msg = template\
            .replace("{name}", first_name)\
            .replace("{days}", str(days_since))\
            .replace("{total_spend}", f"₹{customer.total_spend:,.0f}")\
            .replace("{order_count}", str(customer.order_count or 0))
        customer_channel_str = customer.channel_preference.value if hasattr(customer.channel_preference, 'value') else (customer.channel_preference or channel_str)
        msg = CampaignMessage(
            id=str(uuid.uuid4()), campaign_id=campaign.id, customer_id=customer.id,
            channel=Channel(customer_channel_str), message_text=personalized_msg,
            status=MessageStatus.pending, channel_confidence="medium",
            channel_reasoning="Routed to customer's stored channel preference",
        )
        db.add(msg)
    db.commit()
    return {
        "campaign_id": campaign.id, "name": campaign.name,
        "segment_size": len(customer_ids), "status": "draft",
        "message": f"Campaign '{campaign.name}' created with {len(customer_ids)} personalized messages. Use POST /campaigns/{{id}}/send to launch."
    }


def execute_get_campaign_stats(params: dict, db: Session) -> dict:
    campaign = db.query(Campaign).filter(Campaign.id == str(params["campaign_id"])).first()
    if not campaign:
        return {"error": "Campaign not found"}
    messages = db.query(CampaignMessage).filter(CampaignMessage.campaign_id == campaign.id).all()
    total = len(messages)
    if total == 0:
        return {"campaign_id": campaign.id, "name": campaign.name, "total": 0}
    sent      = sum(1 for m in messages if m.sent_at)
    delivered = sum(1 for m in messages if m.delivered_at)
    opened    = sum(1 for m in messages if m.opened_at)
    clicked   = sum(1 for m in messages if m.clicked_at)
    purchased = sum(1 for m in messages if m.purchased_at)
    failed    = sum(1 for m in messages if m.failed_at)
    def pct(n, d): return round(n / max(d, 1) * 100, 1)
    return {
        "campaign_id": campaign.id, "name": campaign.name,
        "status": campaign.status.value if hasattr(campaign.status, 'value') else campaign.status,
        "total": total, "sent": sent, "delivered": delivered, "opened": opened,
        "clicked": clicked, "purchased": purchased, "failed": failed,
        "delivery_rate": pct(delivered, sent), "open_rate": pct(opened, delivered),
        "click_rate": pct(clicked, opened), "conversion_rate": pct(purchased, clicked),
    }


# ─────────────────────────────────────────────
# TOOL ROUTER
# ─────────────────────────────────────────────

TOOL_MAP = {
    "get_customers":               execute_get_customers,
    "get_customer_profile":        execute_get_customer_profile,
    "get_campaign_history":        execute_get_campaign_history,
    "calculate_revenue_at_risk":   execute_calculate_revenue_at_risk,
    "get_channel_profile":         execute_get_channel_profile,
    "create_segment":              execute_create_segment,
    "create_campaign":             execute_create_campaign,
    "get_campaign_stats":          execute_get_campaign_stats,
}


def coerce_tool_input(tool_name: str, tool_input: dict) -> dict:
    """
    Groq sometimes passes integers as strings e.g. "5" instead of 5.
    This coerces known integer and number fields to the correct type
    so SQLAlchemy and Python don't get type errors.
    """
    integer_fields = {"limit", "days_since_purchase", "min_orders", "min_health_score", "max_health_score"}
    number_fields  = {"min_spend", "max_spend", "estimated_revenue"}

    coerced = {}
    for k, v in tool_input.items():
        if k in integer_fields and isinstance(v, str):
            try:
                coerced[k] = int(v)
            except ValueError:
                coerced[k] = v
        elif k in number_fields and isinstance(v, str):
            try:
                coerced[k] = float(v)
            except ValueError:
                coerced[k] = v
        else:
            coerced[k] = v
    return coerced


def run_tool(tool_name: str, tool_input: dict, db: Session) -> str:
    fn = TOOL_MAP.get(tool_name)
    if not fn:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    try:
        tool_input = coerce_tool_input(tool_name, tool_input)
        result = fn(tool_input, db)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─────────────────────────────────────────────
# ReAct LOOP — GROQ / OpenAI format
#
# OpenAI tool calling format is simpler than Gemini:
# - response.choices[0].message.tool_calls  → list of tool calls
# - each tool_call.function.name            → tool name
# - each tool_call.function.arguments       → JSON string of params
# - append {"role": "tool", "content": result, "tool_call_id": id}
# ─────────────────────────────────────────────

def run_react_loop(messages: list, db: Session, max_iterations: int = 10) -> str:
    system_prompt = """You are ShopPulse's AI marketing agent for Brew & Co., a coffee chain CRM.

Your job: help the marketer reach the right customers with the right message at the right time.

Always:
- Frame everything in rupees (₹), not just percentages
- Check campaign history before recommending — don't repeat past mistakes
- Be specific: segment size, revenue at stake, channel recommendation
- When creating campaigns, always confirm segment + message with marketer first

You have 8 tools. Use them in sequence to build a complete picture before answering.
Never hallucinate customer data — always use tools to get real numbers.

Tone: direct, data-driven, brief."""

    # Build OpenAI-format messages list
    openai_messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history
    for msg in messages:
        if isinstance(msg["content"], str):
            role = "assistant" if msg["role"] == "assistant" else "user"
            openai_messages.append({"role": role, "content": msg["content"]})

    iteration = 0
    while iteration < max_iterations:
        iteration += 1

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=openai_messages,
            tools=TOOLS,
            tool_choice="auto",  # let the model decide when to call tools
            max_tokens=2048,
            temperature=0.2,
        )

        response_message = response.choices[0].message

        # No tool calls → model gave final answer
        if not response_message.tool_calls:
            return response_message.content or "Analysis complete."

        # Add model's response (with tool calls) to history
        openai_messages.append(response_message)

        # Execute each tool call and add results
        for tool_call in response_message.tool_calls:
            tool_name  = tool_call.function.name
            tool_input = json.loads(tool_call.function.arguments)
            result_str = run_tool(tool_name, tool_input, db)

            # Add tool result — OpenAI format
            openai_messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,  # must match the tool_call's id
                "content": result_str,
            })

    return "Analysis complete. What would you like to do next?"


# ─────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────

@router.post("/chat")
async def agent_chat(req: ChatRequest, db: Session = Depends(get_db)):
    messages = list(req.conversation_history)
    messages.append({"role": "user", "content": req.message})
    response_text = run_react_loop(messages, db)
    messages.append({"role": "assistant", "content": response_text})
    return {"response": response_text, "conversation_history": messages}


@router.get("/recommendations")
async def get_recommendations(db: Session = Depends(get_db)):
    at_risk_count = db.query(Customer).filter(Customer.lifecycle_stage == LifecycleStage.at_risk).count()
    loyal_count   = db.query(Customer).filter(Customer.lifecycle_stage == LifecycleStage.loyal).count()
    churned_count = db.query(Customer).filter(Customer.lifecycle_stage == LifecycleStage.churned).count()
    at_risk_spend = db.query(func.sum(Customer.total_spend)).filter(Customer.lifecycle_stage == LifecycleStage.at_risk).scalar() or 0
    loyal_spend   = db.query(func.sum(Customer.total_spend)).filter(Customer.lifecycle_stage == LifecycleStage.loyal).scalar() or 0

    prompt = f"""Brew & Co. CRM snapshot:
- {at_risk_count} at-risk customers (₹{at_risk_spend:,.0f} total historical spend)
- {loyal_count} loyal customers (₹{loyal_spend:,.0f} total historical spend)
- {churned_count} churned customers

Write 3 sharp, revenue-focused opportunity cards.
Return ONLY valid JSON array, no markdown:
[{{"title": "...", "rupees": 50000, "urgency": "high", "action": "...", "segment": "at_risk"}}]"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
        temperature=0.3,
    )
    raw = response.choices[0].message.content.strip()
    cleaned = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        opportunities = json.loads(cleaned)
    except json.JSONDecodeError:
        opportunities = [{"title": raw, "rupees": 0, "urgency": "medium", "action": "Review customers", "segment": "at_risk"}]
    return {"opportunities": opportunities}


@router.post("/create-campaign")
async def create_campaign_from_chat(req: CreateCampaignRequest, db: Session = Depends(get_db)):
    result = execute_create_campaign({
        "name": req.campaign_name,
        **req.segment_criteria,
        "message_template": req.message_template,
        "channel": req.channel,
        "opportunity_type": req.opportunity_type,
        "ai_reasoning": "Created via AI campaign builder"
    }, db)
    return result
