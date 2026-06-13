"""
watching_agent.py — Background Watching Agent
Architecture:
  Detection/logic  → pure Python + SQL (runs every 60s, zero API cost)
  Text generation  → Groq free tier (only fires when something actually needs writing)

This means:
  - campaign_monitor   runs every 60s, calls Groq ONLY when anomaly detected (~rare)
  - opportunity_scanner runs every 60s, calls Groq ONLY if cache is 30+ min old (~48/day)
  - reply_classifier   runs every 60s, calls Groq ONLY for ambiguous replies (~few/day)
  - memory_updater     runs every 60s, calls Groq ONLY when campaign completes (~few/day)

Total Groq calls: ~50-60/day. Groq free tier limit: 1000/day. Plenty of headroom.
"""

import json
import os
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from openai import OpenAI  # Groq uses OpenAI-compatible SDK

from app.core.database import SessionLocal
from app.models.models import (
    Campaign, CampaignMessage, CustomerReply,
    CampaignMemory, Customer,
    CampaignStatus, MessageStatus, ReplyType
)

load_dotenv()

# ─────────────────────────────────────────────
# GROQ CLIENT
# Groq is OpenAI-compatible — same SDK, different base_url + model
# No extra SDK needed: pip install openai
# Get free key at: console.groq.com
# ─────────────────────────────────────────────
groq_client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY", ""),
    base_url="https://api.groq.com/openai/v1"
)

GROQ_MODEL = "openai/gpt-oss-120b"  # best free model on Groq


def groq_generate(prompt: str, max_tokens: int = 300) -> str:
    """
    Single function for all Groq text generation.
    Keeps all AI calls in one place — easy to swap provider later.
    """
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.3,  # low temperature = more consistent, less random
    )
    return response.choices[0].message.content.strip()


scheduler = AsyncIOScheduler()


def get_db_session() -> Session:
    return SessionLocal()


def make_id():
    return str(uuid.uuid4())


# ─────────────────────────────────────────────
# JOB 1: CAMPAIGN MONITOR
#
# DETECTION  → pure math (open_rate < 0.10) — no AI
# TEXT       → Groq writes the 2-sentence alert — only when anomaly found
#
# Runs every 60s. Groq only called if there's a live campaign with an anomaly.
# In a demo with 1-2 campaigns, this is maybe 1-2 Groq calls total.
# ─────────────────────────────────────────────

async def campaign_monitor():
    db = get_db_session()
    try:
        live_campaigns = db.query(Campaign)\
                           .filter(Campaign.status == CampaignStatus.live)\
                           .all()

        for campaign in live_campaigns:
            messages = db.query(CampaignMessage)\
                         .filter(CampaignMessage.campaign_id == campaign.id)\
                         .all()

            total     = len(messages)
            delivered = sum(1 for m in messages if m.delivered_at)
            opened    = sum(1 for m in messages if m.opened_at)
            failed    = sum(1 for m in messages if m.failed_at)

            # ── PURE MATH DETECTION — zero AI ──
            if delivered < 50:
                continue  # not enough data yet

            open_rate    = opened / max(delivered, 1)
            failure_rate = failed / max(total, 1)

            anomalies = []
            if open_rate < 0.10:
                anomalies.append(f"Low open rate: {open_rate:.1%} (expected >20%)")
            if failure_rate > 0.30:
                anomalies.append(f"High failure rate: {failure_rate:.1%} (expected <15%)")

            if not anomalies:
                continue  # no anomaly — skip, zero AI calls this run

            # ── GROQ CALLED ONLY HERE — anomaly confirmed ──
            prompt = f"""Campaign '{campaign.name}' anomaly detected:
{chr(10).join(anomalies)}
Stats: {delivered} delivered, {opened} opened, {failed} failed of {total} total.
In 2 sentences: what might be wrong and what should the marketer do right now?"""

            alert_text = groq_generate(prompt, max_tokens=150)

            # Write alert to CampaignMemory
            memory = db.query(CampaignMemory)\
                       .filter(CampaignMemory.campaign_id == campaign.id)\
                       .first()

            if not memory:
                memory = CampaignMemory(
                    id=make_id(),
                    campaign_id=campaign.id,
                    segment_type=campaign.opportunity_type,
                    channel_used="mixed",
                    timing_used="varied",
                    open_rate=open_rate,
                    learnings={
                        "anomaly_alert": alert_text,
                        "detected_at": datetime.utcnow().isoformat()
                    }
                )
                db.add(memory)
            else:
                existing = memory.learnings or {}
                existing["anomaly_alert"] = alert_text
                existing["detected_at"] = datetime.utcnow().isoformat()
                memory.learnings = existing
                memory.open_rate = open_rate

            db.commit()
            print(f"[WatchingAgent] Anomaly alert written for: {campaign.name}")

    except Exception as e:
        print(f"[WatchingAgent] campaign_monitor error: {e}")
    finally:
        db.close()


# ─────────────────────────────────────────────
# JOB 2: OPPORTUNITY SCANNER
#
# DETECTION  → pure SQL aggregates — no AI
#   Counts customers per stage, sums their spend
#   This is just SELECT COUNT + SUM queries
#
# TEXT       → Groq writes the 3 opportunity card descriptions
#   But ONLY if cache is older than 30 minutes
#   So Groq fires ~48 times/day max, not 1440 times
#
# opportunity_cache is an in-memory dict shared with opportunities.py
# ─────────────────────────────────────────────

opportunity_cache = {
    "opportunities": [],
    "last_updated": None,
    # Pure SQL snapshot — always fresh, no AI needed
    "raw_stats": {}
}

# How long before we refresh the AI-generated descriptions
CACHE_TTL_MINUTES = 30


async def opportunity_scanner():
    db = get_db_session()
    try:
        # ── PURE SQL — runs every 60s, zero AI cost ──
        segments = {}
        for stage in ["at_risk", "churned", "loyal", "new", "growing"]:
            count = db.query(Customer)\
                      .filter(Customer.lifecycle_stage == stage)\
                      .count()
            spend = db.query(func.sum(Customer.total_spend))\
                      .filter(Customer.lifecycle_stage == stage)\
                      .scalar() or 0
            segments[stage] = {
                "count": count,
                "total_spend": round(float(spend), 2)
            }

        # Always update raw stats (pure SQL, free)
        opportunity_cache["raw_stats"] = segments

        # ── CHECK CACHE AGE ──
        last_updated = opportunity_cache.get("last_updated")
        if last_updated:
            age_minutes = (datetime.utcnow() - last_updated).seconds / 60
            if age_minutes < CACHE_TTL_MINUTES:
                # Cache is fresh — skip Groq entirely this run
                return

        # ── GROQ CALLED ONLY HERE — cache is stale or empty ──
        # ── GROQ CALLED ONLY HERE — cache is stale or empty ──
        at_risk = segments["at_risk"]
        churned = segments["churned"]
        loyal   = segments["loyal"]

        prompt = f"""You must respond with ONLY a JSON array, nothing else. No explanation, no markdown.

Brew & Co. coffee chain data:
- At-risk customers: {at_risk['count']}, total spend ₹{at_risk['total_spend']:,.0f}
- Churned customers: {churned['count']}, total spend ₹{churned['total_spend']:,.0f}
- Loyal customers: {loyal['count']}, total spend ₹{loyal['total_spend']:,.0f}

Respond with exactly this structure:
[{{"title": "string", "rupees": 50000, "urgency": "high", "action": "string", "segment": "at_risk", "reasoning": "string"}}, {{"title": "string", "rupees": 30000, "urgency": "medium", "action": "string", "segment": "loyal", "reasoning": "string"}}, {{"title": "string", "rupees": 20000, "urgency": "low", "action": "string", "segment": "churned", "reasoning": "string"}}]"""

        raw = groq_generate(prompt, max_tokens=600)
        print(f"[WatchingAgent] raw response: {raw[:200]}") 

        cleaned = raw.strip()
        if "```" in cleaned:
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        start = cleaned.find("[")
        end = cleaned.rfind("]") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON array found in response")
        cleaned = cleaned[start:end]

        opportunities = json.loads(cleaned)
        opportunity_cache["opportunities"] = opportunities
        opportunity_cache["last_updated"] = datetime.utcnow()
        print(f"[WatchingAgent] Opportunity cache refreshed")

    except Exception as e:
        print(f"[WatchingAgent] opportunity_scanner error: {e}")
    finally:
        db.close()


# ─────────────────────────────────────────────
# JOB 3: REPLY CLASSIFIER
#
# DETECTION  → keyword matching — no AI (handles ~80% of replies)
#   "stop", "unsubscribe" → unsubscribe (pure string check)
#   "hours", "where"      → simple (pure string check)
#
# TEXT       → Groq classifies ONLY the remaining ~20% ambiguous replies
#   In a demo, maybe 2-3 replies total need this
# ─────────────────────────────────────────────

UNSUBSCRIBE_KEYWORDS = ["stop", "unsubscribe", "opt out", "remove me", "don't message"]
SIMPLE_KEYWORDS      = ["when", "what time", "hours", "open", "near me", "where", "how"]


async def reply_classifier():
    db = get_db_session()
    try:
        unprocessed = db.query(CustomerReply)\
                        .filter(
                            CustomerReply.auto_responded == False,
                            CustomerReply.flagged_to_marketer == False
                        )\
                        .limit(20).all()

        for reply in unprocessed:
            msg_lower = reply.message.lower()

            # ── PURE KEYWORD DETECTION — zero AI ──
            if any(kw in msg_lower for kw in UNSUBSCRIBE_KEYWORDS):
                reply.reply_type = ReplyType.unsubscribe
                reply.auto_responded = True
                reply.auto_response_text = "You've been unsubscribed from Brew & Co. messages. We'll miss you ☕"

            elif any(kw in msg_lower for kw in SIMPLE_KEYWORDS):
                reply.reply_type = ReplyType.simple
                reply.auto_responded = True
                reply.auto_response_text = "Hi! Brew & Co. is open daily 7AM–10PM. Find your nearest store at brewandco.in/stores 🗺️"

            else:
                # ── GROQ CALLED ONLY HERE — ambiguous reply ──
                prompt = f"""Customer reply to a marketing message: "{reply.message}"
Classify as ONE of: simple, sensitive, unsubscribe
Reply with just the single word, nothing else."""

                try:
                    classification = groq_generate(prompt, max_tokens=5).lower()

                    if "unsubscribe" in classification:
                        reply.reply_type = ReplyType.unsubscribe
                        reply.auto_responded = True
                        reply.auto_response_text = "You've been unsubscribed. We'll miss you ☕"
                    elif "simple" in classification:
                        reply.reply_type = ReplyType.simple
                        reply.auto_responded = True
                        reply.auto_response_text = "Thanks for reaching out! Visit brewandco.in for help."
                    else:
                        reply.reply_type = ReplyType.sensitive
                        reply.flagged_to_marketer = True

                except Exception:
                    # If Groq fails, flag for safety — never auto-respond on failure
                    reply.flagged_to_marketer = True

            db.commit()

    except Exception as e:
        print(f"[WatchingAgent] reply_classifier error: {e}")
    finally:
        db.close()


# ─────────────────────────────────────────────
# JOB 4: MEMORY UPDATER
#
# DETECTION  → pure SQL
#   Find completed campaigns with no memory yet
#   Calculate open_rate, click_rate, conversion_rate — pure math
#
# TEXT       → Groq writes what_worked / what_didnt / next_time
#   Only fires when a campaign completes — maybe 2-3 times in a demo
# ─────────────────────────────────────────────

async def memory_updater():
    db = get_db_session()
    try:
        # ── PURE SQL DETECTION — zero AI ──
        completed_without_memory = db.query(Campaign)\
            .filter(Campaign.status == CampaignStatus.completed)\
            .outerjoin(CampaignMemory, CampaignMemory.campaign_id == Campaign.id)\
            .filter(CampaignMemory.id == None)\
            .all()

        for campaign in completed_without_memory:
            messages = db.query(CampaignMessage)\
                         .filter(CampaignMessage.campaign_id == campaign.id)\
                         .all()

            total = len(messages)
            if total == 0:
                continue

            # ── PURE MATH — zero AI ──
            delivered = sum(1 for m in messages if m.delivered_at)
            opened    = sum(1 for m in messages if m.opened_at)
            clicked   = sum(1 for m in messages if m.clicked_at)
            purchased = sum(1 for m in messages if m.purchased_at)

            open_rate       = opened    / max(delivered, 1)
            click_rate      = clicked   / max(opened, 1)
            conversion_rate = purchased / max(clicked, 1)

            # Revenue estimate — pure math
            purchased_ids = [m.customer_id for m in messages if m.purchased_at]
            revenue = 0.0
            if purchased_ids:
                converted = db.query(Customer)\
                              .filter(Customer.id.in_(purchased_ids))\
                              .all()
                if converted:
                    avg_order = sum(
                        c.total_spend / max(c.order_count, 1)
                        for c in converted
                    ) / len(converted)
                    revenue = len(purchased_ids) * avg_order

            # ── GROQ CALLED ONLY HERE — writing learnings text ──
            prompt = f"""Campaign '{campaign.name}' just completed.
Type: {campaign.opportunity_type}
Stats: Sent {total}, Delivered {delivered}, Open rate {open_rate:.1%}, Click rate {click_rate:.1%}, Conversion {conversion_rate:.1%}, Revenue ₹{revenue:,.0f}
AI reasoning when created: {campaign.ai_reasoning or 'Not recorded'}

Generate a learnings JSON with exactly 3 keys:
- what_worked: one sentence
- what_didnt: one sentence
- next_time: one concrete suggestion
Return ONLY valid JSON, no markdown."""

            try:
                raw = groq_generate(prompt, max_tokens=200)
                cleaned = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                learnings = json.loads(cleaned)
            except Exception:
                # Fallback — pure text, no AI needed
                learnings = {
                    "what_worked":  f"Reached {delivered} customers, {open_rate:.0%} open rate",
                    "what_didnt":   f"Conversion at {conversion_rate:.0%} — room to improve",
                    "next_time":    "Test a stronger CTA and different send time"
                }

            # Primary channel — pure Python
            channel_counts = {}
            for m in messages:
                ch = m.channel.value if hasattr(m.channel, 'value') else m.channel
                channel_counts[ch] = channel_counts.get(ch, 0) + 1
            primary_channel = max(channel_counts, key=channel_counts.get) if channel_counts else "whatsapp"

            memory = CampaignMemory(
                id=make_id(),
                campaign_id=campaign.id,
                segment_type=campaign.opportunity_type,
                channel_used=primary_channel,
                timing_used="varied",
                open_rate=open_rate,
                click_rate=click_rate,
                conversion_rate=conversion_rate,
                revenue_recovered=revenue,
                learnings=learnings,
                created_at=datetime.utcnow()
            )
            db.add(memory)
            db.commit()
            print(f"[WatchingAgent] Memory written for: {campaign.name}")

    except Exception as e:
        print(f"[WatchingAgent] memory_updater error: {e}")
    finally:
        db.close()


# ─────────────────────────────────────────────
# SCHEDULER SETUP
# Back to 60s — safe now because 99% of runs make zero AI calls
# ─────────────────────────────────────────────

def start_watching_agent():
    scheduler.add_job(campaign_monitor,    "interval", seconds=60, id="campaign_monitor")
    scheduler.add_job(opportunity_scanner, "interval", seconds=60, id="opportunity_scanner",
                      next_run_time=datetime.utcnow())  # run immediately on startup
    scheduler.add_job(reply_classifier,    "interval", seconds=60, id="reply_classifier")
    scheduler.add_job(memory_updater,      "interval", seconds=60, id="memory_updater")
    scheduler.start()
    print("[WatchingAgent] Started — 4 jobs at 60s, AI only when needed")


def stop_watching_agent():
    if scheduler.running:
        scheduler.shutdown()
    print("[WatchingAgent] Stopped")


def get_cached_opportunities():
    return opportunity_cache
