"""
Seed script for Brew & Co. — a fictional coffee chain with 500 customers.
Designed so every AI feature has meaningful data to work with.
Run: python -m app.core.seed
"""

import uuid
import random
from datetime import datetime, timedelta
from faker import Faker
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app.models.models import (
    Base, Customer, Order, Campaign, CampaignMessage, CampaignMemory,
    LifecycleStage, Channel, CampaignStatus, MessageStatus
)

fake = Faker("en_IN")
random.seed(42)

PRODUCTS = [
    ("Cold Brew (500ml)", 180),
    ("Espresso Shot", 90),
    ("Cappuccino", 150),
    ("Latte", 170),
    ("Mocha", 200),
    ("Filter Coffee", 80),
    ("Cold Coffee", 160),
    ("Nitro Brew", 220),
    ("Oat Milk Latte", 210),
    ("Iced Americano", 140),
    ("Cortado", 130),
    ("Flat White", 190),
    ("Monthly Brew Box (1kg)", 950),
    ("Brew Kit (Gift)", 1200),
    ("Coffee Subscription (3 months)", 2100),
]


def make_id():
    return str(uuid.uuid4())


def random_date(start_days_ago: int, end_days_ago: int = 0) -> datetime:
    days = random.randint(end_days_ago, start_days_ago)
    return datetime.utcnow() - timedelta(days=days)


def assign_lifecycle(last_purchase_date: datetime, order_count: int, total_spend: float) -> LifecycleStage:
    days_since = (datetime.utcnow() - last_purchase_date).days
    if days_since > 90:
        return LifecycleStage.churned
    if days_since > 45:
        return LifecycleStage.at_risk
    if order_count >= 8 or total_spend >= 2000:
        return LifecycleStage.loyal
    if order_count >= 3:
        return LifecycleStage.growing
    return LifecycleStage.new


def compute_health_score(last_purchase_date: datetime, order_count: int, total_spend: float) -> int:
    days_since = (datetime.utcnow() - last_purchase_date).days
    recency_score = max(0, 40 - days_since // 3)
    frequency_score = min(30, order_count * 3)
    value_score = min(30, int(total_spend / 100))
    return min(100, recency_score + frequency_score + value_score)


def seed_customers(db: Session) -> list[Customer]:
    customers = []

    # Segment distribution (out of 500):
    # 120 loyal (high spend, frequent)
    # 80 growing (moderate)
    # 100 new (recent, few orders)
    # 130 at_risk (haven't bought in 45-90 days)
    # 70 churned (90+ days silent)

    segments = (
        [("loyal", 8, 20, 500, 3000, 1, 30)] * 120 +
        [("growing", 3, 7, 200, 1200, 15, 60)] * 80 +
        [("new", 1, 2, 80, 400, 1, 20)] * 100 +
        [("at_risk", 2, 8, 200, 1500, 50, 90)] * 130 +
        [("churned", 1, 5, 100, 800, 91, 180)] * 70
    )

    for i, (seg, min_orders, max_orders, min_spend, max_spend, min_days, max_days) in enumerate(segments):
        customer_id = make_id()
        channel = Channel.whatsapp if random.random() > 0.35 else Channel.sms
        last_purchase = random_date(max_days, min_days)

        customer = Customer(
            id=customer_id,
            name=fake.name(),
            phone=f"+91{random.randint(7000000000, 9999999999)}",
            email=fake.email() if random.random() > 0.3 else None,
            channel_preference=channel,
            total_spend=0.0,
            order_count=0,
            last_purchase_date=last_purchase,
            lifecycle_stage=LifecycleStage.new,
            health_score=50,
        )
        customers.append(customer)

    db.add_all(customers)
    db.flush()
    return customers


def seed_orders(db: Session, customers: list[Customer]) -> list[Order]:
    """Seed ~1847 orders across 6 months"""
    orders = []

    # Map lifecycle to order profile
    order_profile = {
        LifecycleStage.loyal: (8, 20, 45, 200),
        LifecycleStage.growing: (3, 7, 90, 500),
        LifecycleStage.new: (1, 2, 1, 25),
        LifecycleStage.at_risk: (2, 8, 50, 200),
        LifecycleStage.churned: (1, 5, 91, 365),
    }

    for customer in customers:
        stage = customer.lifecycle_stage
        min_o, max_o, min_d, max_d = order_profile.get(stage, (1, 3, 30, 180))

        # Recompute since we don't have assigned stage yet
        days_since_last = (datetime.utcnow() - customer.last_purchase_date).days
        if days_since_last > 90:
            num_orders = random.randint(1, 5)
        elif days_since_last > 45:
            num_orders = random.randint(2, 8)
        elif customer.last_purchase_date > datetime.utcnow() - timedelta(days=20):
            num_orders = random.randint(1, 20)
        else:
            num_orders = random.randint(3, 7)

        total_spend = 0.0
        for j in range(num_orders):
            product_name, base_price = random.choice(PRODUCTS)
            amount = base_price + random.randint(-10, 30)

            if j == 0:
                # Most recent order anchored to last_purchase_date
                purchase_date = customer.last_purchase_date
            else:
                days_back = random.randint(1, min(180, days_since_last + 160))
                purchase_date = datetime.utcnow() - timedelta(days=days_back)

            order = Order(
                id=make_id(),
                customer_id=customer.id,
                product_name=product_name,
                amount=float(amount),
                purchased_at=purchase_date,
            )
            orders.append(order)
            total_spend += amount

        customer.total_spend = round(total_spend, 2)
        customer.order_count = num_orders
        customer.lifecycle_stage = assign_lifecycle(customer.last_purchase_date, num_orders, total_spend)
        customer.health_score = compute_health_score(customer.last_purchase_date, num_orders, total_spend)

    db.add_all(orders)
    db.flush()
    return orders


def seed_past_campaigns(db: Session, customers: list[Customer]) -> list[Campaign]:
    """12 past campaigns with realistic outcomes stored as CampaignMemories"""

    past_campaigns_config = [
        {
            "name": "Win-Back: Silent Loyals (Mar)",
            "type": "lapsed",
            "segment": {"lifecycle_stage": "at_risk", "min_spend": 1000},
            "days_ago": 90,
            "open_rate": 0.52,
            "click_rate": 0.28,
            "conversion_rate": 0.18,
            "revenue": 34200,
            "channel": "whatsapp",
            "timing": "Tuesday 10AM",
            "learnings": {
                "what_worked": "Personal tone with spend history mentioned performed 2x better",
                "what_didnt": "Generic 'we miss you' messages had 3% click rate",
                "next_time": "Always mention their last purchase in the opening line",
            },
        },
        {
            "name": "Loyalty Reward — April",
            "type": "primed",
            "segment": {"lifecycle_stage": "loyal"},
            "days_ago": 60,
            "open_rate": 0.68,
            "click_rate": 0.41,
            "conversion_rate": 0.29,
            "revenue": 58700,
            "channel": "whatsapp",
            "timing": "Friday 5PM",
            "learnings": {
                "what_worked": "Friday evenings hit 1.8x better open rates for loyal segment",
                "what_didnt": "Discount-first messaging underperformed — loyals don't need discounts",
                "next_time": "Lead with exclusivity, not discount, for loyal customers",
            },
        },
        {
            "name": "New Brew Box Launch",
            "type": "primed",
            "segment": {"lifecycle_stage": "growing", "min_orders": 3},
            "days_ago": 45,
            "open_rate": 0.44,
            "click_rate": 0.22,
            "conversion_rate": 0.12,
            "revenue": 21300,
            "channel": "sms",
            "timing": "Monday 11AM",
            "learnings": {
                "what_worked": "SMS had surprisingly good CTR for product launches",
                "what_didnt": "Long messages got truncated — keep SMS under 160 chars",
                "next_time": "For SMS, use a single clear CTA and a shortened link",
            },
        },
        {
            "name": "Churn Recovery — May",
            "type": "lapsed",
            "segment": {"lifecycle_stage": "churned", "days_since_purchase": 100},
            "days_ago": 38,
            "open_rate": 0.31,
            "click_rate": 0.12,
            "conversion_rate": 0.07,
            "revenue": 8900,
            "channel": "whatsapp",
            "timing": "Sunday 11AM",
            "learnings": {
                "what_worked": "Offering free coffee sample link got 3x clicks",
                "what_didnt": "Sending on Sunday had lower open rates than expected",
                "next_time": "For churned customers, Tuesday 10AM performs better than weekends",
            },
        },
        {
            "name": "Weekend Flash — Cold Brew",
            "type": "primed",
            "segment": {"product_affinity": "Cold Brew"},
            "days_ago": 30,
            "open_rate": 0.61,
            "click_rate": 0.38,
            "conversion_rate": 0.24,
            "revenue": 29100,
            "channel": "whatsapp",
            "timing": "Friday 4PM",
            "learnings": {
                "what_worked": "Product-specific messaging to fans of that product had 60%+ open rate",
                "what_didnt": "Only 24hr urgency window limited reach",
                "next_time": "48hr window for flash sales performs better",
            },
        },
        {
            "name": "Re-engage Growers",
            "type": "lapsed",
            "segment": {"lifecycle_stage": "growing", "days_since_purchase": 30},
            "days_ago": 22,
            "open_rate": 0.39,
            "click_rate": 0.19,
            "conversion_rate": 0.11,
            "revenue": 14600,
            "channel": "sms",
            "timing": "Wednesday 7PM",
            "learnings": {
                "what_worked": "Evening timing worked well for growing segment (working professionals)",
                "what_didnt": "Generic message without purchase reference underperformed",
                "next_time": "Always personalise with last product name for growing customers",
            },
        },
        {
            "name": "Subscription Upsell",
            "type": "primed",
            "segment": {"lifecycle_stage": "loyal", "order_count_min": 10},
            "days_ago": 18,
            "open_rate": 0.71,
            "click_rate": 0.44,
            "conversion_rate": 0.33,
            "revenue": 72400,
            "channel": "whatsapp",
            "timing": "Tuesday 9AM",
            "learnings": {
                "what_worked": "Subscription framing ('save ₹800/month') massively outperformed % discount",
                "what_didnt": "Too long a message — first 2 lines carry 80% of the conversion",
                "next_time": "Lead with rupee savings, not % off. Keep to 3 sentences max",
            },
        },
        {
            "name": "Mothers Day Special",
            "type": "primed",
            "segment": {"all": True},
            "days_ago": 32,
            "open_rate": 0.55,
            "click_rate": 0.29,
            "conversion_rate": 0.16,
            "revenue": 44800,
            "channel": "whatsapp",
            "timing": "Wednesday 10AM",
            "learnings": {
                "what_worked": "Gift angle drove high intent clicks — Brew Kit sold out",
                "what_didnt": "Sent to churned customers too — wasted slots",
                "next_time": "Exclude churned (>90 days) from seasonal campaigns",
            },
        },
        {
            "name": "At-Risk Rescue — Week 1",
            "type": "lapsed",
            "segment": {"lifecycle_stage": "at_risk"},
            "days_ago": 14,
            "open_rate": 0.43,
            "click_rate": 0.21,
            "conversion_rate": 0.13,
            "revenue": 19200,
            "channel": "whatsapp",
            "timing": "Monday 10AM",
            "learnings": {
                "what_worked": "Mentioning days since last visit ('it's been 47 days') drove empathy clicks",
                "what_didnt": "Discount of 10% was too low — 20% had 2x conversion in A/B",
                "next_time": "Start at 20% for at-risk. 10% feels like an afterthought",
            },
        },
        {
            "name": "New Member Welcome",
            "type": "primed",
            "segment": {"lifecycle_stage": "new", "days_since_join": 3},
            "days_ago": 10,
            "open_rate": 0.77,
            "click_rate": 0.48,
            "conversion_rate": 0.31,
            "revenue": 9300,
            "channel": "whatsapp",
            "timing": "Same day as first purchase",
            "learnings": {
                "what_worked": "Day-of-first-purchase message had 77% open rate — highest ever",
                "what_didnt": "Too product-heavy — should be warmer / community feel first time",
                "next_time": "Welcome message: story first, product second",
            },
        },
        {
            "name": "Nitro Brew Launch",
            "type": "primed",
            "segment": {"product_affinity": "Cold Brew", "channel": "whatsapp"},
            "days_ago": 7,
            "open_rate": 0.59,
            "click_rate": 0.35,
            "conversion_rate": 0.21,
            "revenue": 26700,
            "channel": "whatsapp",
            "timing": "Thursday 12PM",
            "learnings": {
                "what_worked": "Lunch-hour send for food/drink products works consistently",
                "what_didnt": "SMS split test got 30% lower open rate for product launch",
                "next_time": "WhatsApp > SMS for product launches — always",
            },
        },
        {
            "name": "Mid-Year Loyalty Thank You",
            "type": "primed",
            "segment": {"lifecycle_stage": "loyal"},
            "days_ago": 4,
            "open_rate": 0.65,
            "click_rate": 0.39,
            "conversion_rate": 0.25,
            "revenue": 51200,
            "channel": "whatsapp",
            "timing": "Friday 6PM",
            "learnings": {
                "what_worked": "Personal thank you with exact order count ('your 23rd cup') hit emotionally",
                "what_didnt": "Generic segment-level thank you got skipped",
                "next_time": "Use exact personalised stats in every loyal customer message",
            },
        },
    ]

    campaigns = []
    memories = []

    # Sample customers for fake campaign message records
    all_customer_ids = [c.id for c in customers]

    for config in past_campaigns_config:
        campaign_id = make_id()
        days_ago = config["days_ago"]
        created = datetime.utcnow() - timedelta(days=days_ago)

        campaign = Campaign(
            id=campaign_id,
            name=config["name"],
            opportunity_type=config["type"],
            segment_criteria=config["segment"],
            total_customers=random.randint(80, 240),
            status=CampaignStatus.completed,
            scheduled_at=created + timedelta(hours=1),
            sent_at=created + timedelta(hours=1),
            completed_at=created + timedelta(hours=3),
            created_at=created,
            estimated_revenue=config["revenue"],
        )
        campaigns.append(campaign)

        memory = CampaignMemory(
            id=make_id(),
            campaign_id=campaign_id,
            segment_type=config["type"],
            channel_used=config["channel"],
            timing_used=config["timing"],
            open_rate=config["open_rate"],
            click_rate=config["click_rate"],
            conversion_rate=config["conversion_rate"],
            revenue_recovered=config["revenue"],
            learnings=config["learnings"],
        )
        memories.append(memory)

    db.add_all(campaigns)
    db.flush()
    db.add_all(memories)
    db.flush()
    return campaigns


def run_seed():
    print("🌱 Seeding Brew & Co. data...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Idempotency: skip if already seeded
        existing = db.query(Customer).count()
        if existing > 0:
            print(f"✅ Already seeded ({existing} customers found). Skipping.")
            return

        print("  → Creating 500 customers...")
        customers = seed_customers(db)

        print("  → Creating ~1847 orders...")
        orders = seed_orders(db, customers)

        print("  → Creating 12 past campaigns with memories...")
        campaigns = seed_past_campaigns(db, customers)

        db.commit()

        # Summary
        total_orders = db.query(Order).count()
        print(f"\n✅ Seeded successfully!")
        print(f"   Customers: {db.query(Customer).count()}")
        print(f"   Orders: {total_orders}")
        print(f"   Campaigns: {db.query(Campaign).count()}")

        stage_counts = {}
        for c in db.query(Customer).all():
            stage_counts[c.lifecycle_stage.value] = stage_counts.get(c.lifecycle_stage.value, 0) + 1
        print(f"   Lifecycle breakdown: {stage_counts}")

    except Exception as e:
        db.rollback()
        print(f"❌ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
