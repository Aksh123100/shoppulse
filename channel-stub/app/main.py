"""
Channel Stub Service

Receives messages from the CRM, simulates delivery outcomes asynchronously,
and fires callbacks back to CRM with status updates.

Callback lifecycle per message:
  1. CRM → POST /send           (stub receives)
  2. Stub → POST /callback/delivery {status: delivered|failed}   (1-5s delay)
  3. If delivered → POST /callback/delivery {status: opened}     (10-60s delay, 45% chance)
  4. If opened   → POST /callback/delivery {status: clicked}     (10-30s delay, 40% chance)
  5. If clicked  → POST /callback/delivery {status: purchased}   (5-20s delay, 35% chance)
  6. If delivered → POST /callback/reply                         (15% chance, 30-120s delay)
"""

import asyncio
import random
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

app = FastAPI(title="ShopPulse Channel Stub", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Simulation probabilities ---
DELIVERY_RATE = 0.82       # 82% delivered
OPEN_RATE = 0.45           # 45% of delivered
CLICK_RATE = 0.40          # 40% of opened
PURCHASE_RATE = 0.35       # 35% of clicked
REPLY_RATE = 0.15          # 15% of delivered get a reply

REPLY_TEMPLATES = {
    "simple": [
        "Is this still available?",
        "How do I redeem this offer?",
        "Thanks! Will visit soon.",
        "Can I use this with my existing points?",
        "Which outlets is this valid at?",
    ],
    "sensitive": [
        "This is spam. Please stop messaging me.",
        "I never signed up for this. Remove me.",
        "This is very annoying.",
    ],
    "unsubscribe": [
        "STOP",
        "Unsubscribe",
        "Stop messaging me",
        "Remove me from your list",
    ],
}


class SendPayload(BaseModel):
    message_id: str
    campaign_id: str
    customer_id: str
    phone: str
    channel: str  # whatsapp / sms
    message_text: str
    callback_url: str
    reply_callback_url: str


async def fire_callback(url: str, payload: dict, delay_seconds: float):
    """Fire a single callback after a delay"""
    await asyncio.sleep(delay_seconds)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            print(f"[stub] Callback {payload.get('status', 'reply')} → {resp.status_code} for msg {payload.get('message_id', '')}")
    except Exception as e:
        print(f"[stub] Callback failed: {e}")


async def simulate_message_lifecycle(payload: SendPayload):
    """Full async simulation of a message's lifecycle"""

    # Step 1: Delivery outcome (1-5s)
    delivery_delay = random.uniform(1, 5)
    delivered = random.random() < DELIVERY_RATE
    status = "delivered" if delivered else "failed"

    await fire_callback(payload.callback_url, {
        "message_id": payload.message_id,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
    }, delivery_delay)

    if not delivered:
        return  # Dead end for failed messages

    # Step 2: Open (10-90s after delivery, 45% chance)
    if random.random() < OPEN_RATE:
        open_delay = random.uniform(10, 90)
        await fire_callback(payload.callback_url, {
            "message_id": payload.message_id,
            "status": "opened",
            "timestamp": datetime.utcnow().isoformat(),
        }, open_delay)

        # Step 3: Click (10-30s after open, 40% chance)
        if random.random() < CLICK_RATE:
            click_delay = open_delay + random.uniform(10, 30)
            await fire_callback(payload.callback_url, {
                "message_id": payload.message_id,
                "status": "clicked",
                "timestamp": datetime.utcnow().isoformat(),
            }, click_delay)

            # Step 4: Purchase (5-20s after click, 35% chance)
            if random.random() < PURCHASE_RATE:
                purchase_delay = click_delay + random.uniform(5, 20)
                await fire_callback(payload.callback_url, {
                    "message_id": payload.message_id,
                    "status": "purchased",
                    "timestamp": datetime.utcnow().isoformat(),
                }, purchase_delay)

    # Step 5: Reply (15% of delivered, 30-120s)
    if random.random() < REPLY_RATE:
        reply_delay = random.uniform(30, 120)

        # Determine reply type
        r = random.random()
        if r < 0.05:
            reply_type = "unsubscribe"
            message = random.choice(REPLY_TEMPLATES["unsubscribe"])
        elif r < 0.15:
            reply_type = "sensitive"
            message = random.choice(REPLY_TEMPLATES["sensitive"])
        else:
            reply_type = "simple"
            message = random.choice(REPLY_TEMPLATES["simple"])

        await fire_callback(payload.reply_callback_url, {
            "message_id": payload.message_id,
            "customer_id": payload.customer_id,
            "campaign_id": payload.campaign_id,
            "message": message,
            "reply_type": reply_type,
        }, reply_delay)


@app.post("/send")
async def receive_message(payload: SendPayload):
    """
    CRM sends message here. We acknowledge immediately and simulate in background.
    This is the "fire and forget" pattern — the CRM never blocks on delivery.
    """
    # Non-blocking: schedule simulation as a background task
    asyncio.create_task(simulate_message_lifecycle(payload))

    return {
        "ok": True,
        "message_id": payload.message_id,
        "channel": payload.channel,
        "accepted_at": datetime.utcnow().isoformat(),
    }


@app.get("/health")
def health():
    return {"status": "healthy", "service": "xeno-channel-stub"}


@app.get("/")
def root():
    return {"service": "xeno-channel-stub", "status": "ok"}
