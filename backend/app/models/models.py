from sqlalchemy import (
    Column, String, Integer, Float, Boolean,
    DateTime, ForeignKey, JSON, Enum as SAEnum, Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class LifecycleStage(str, enum.Enum):
    new = "new"
    growing = "growing"
    loyal = "loyal"
    at_risk = "at_risk"
    churned = "churned"


class Channel(str, enum.Enum):
    whatsapp = "whatsapp"
    sms = "sms"


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    live = "live"
    completed = "completed"


class MessageStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    delivered = "delivered"
    failed = "failed"
    opened = "opened"
    clicked = "clicked"
    purchased = "purchased"


class ReplyType(str, enum.Enum):
    simple = "simple"
    sensitive = "sensitive"
    unsubscribe = "unsubscribe"


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=True)
    channel_preference = Column(SAEnum(Channel), default=Channel.whatsapp)
    total_spend = Column(Float, default=0.0)
    order_count = Column(Integer, default=0)
    last_purchase_date = Column(DateTime, nullable=True)
    lifecycle_stage = Column(SAEnum(LifecycleStage), default=LifecycleStage.new)
    health_score = Column(Integer, default=50)  # 0-100
    created_at = Column(DateTime, server_default=func.now())

    orders = relationship("Order", back_populates="customer", cascade="all, delete-orphan")
    campaign_messages = relationship("CampaignMessage", back_populates="customer")
    replies = relationship("CustomerReply", back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    product_name = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    purchased_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    customer = relationship("Customer", back_populates="orders")


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    opportunity_type = Column(String, nullable=False)  # lapsed / primed / retry / custom
    segment_criteria = Column(JSON, nullable=False)
    total_customers = Column(Integer, default=0)
    status = Column(SAEnum(CampaignStatus), default=CampaignStatus.draft)
    scheduled_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # AI-generated metadata
    ai_reasoning = Column(Text, nullable=True)
    estimated_revenue = Column(Float, default=0.0)

    messages = relationship("CampaignMessage", back_populates="campaign", cascade="all, delete-orphan")
    memory = relationship("CampaignMemory", back_populates="campaign", uselist=False)
    replies = relationship("CustomerReply", back_populates="campaign")


class CampaignMessage(Base):
    __tablename__ = "campaign_messages"

    id = Column(String, primary_key=True)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    channel = Column(SAEnum(Channel), nullable=False)
    message_text = Column(Text, nullable=False)
    scheduled_at = Column(DateTime, nullable=True)
    status = Column(SAEnum(MessageStatus), default=MessageStatus.pending)

    # Timestamps for each state transition
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    purchased_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)

    # Channel intelligence metadata
    channel_confidence = Column(String, default="low")  # low / medium / high
    channel_reasoning = Column(Text, nullable=True)

    campaign = relationship("Campaign", back_populates="messages")
    customer = relationship("Customer", back_populates="campaign_messages")


class CustomerReply(Base):
    __tablename__ = "customer_replies"

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    message = Column(Text, nullable=False)
    reply_type = Column(SAEnum(ReplyType), default=ReplyType.simple)
    auto_responded = Column(Boolean, default=False)
    auto_response_text = Column(Text, nullable=True)
    flagged_to_marketer = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    customer = relationship("Customer", back_populates="replies")
    campaign = relationship("Campaign", back_populates="replies")


class CampaignMemory(Base):
    __tablename__ = "campaign_memories"

    id = Column(String, primary_key=True)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False, unique=True)
    segment_type = Column(String, nullable=False)
    channel_used = Column(String, nullable=False)
    timing_used = Column(String, nullable=True)

    # Outcomes
    open_rate = Column(Float, default=0.0)
    click_rate = Column(Float, default=0.0)
    conversion_rate = Column(Float, default=0.0)
    revenue_recovered = Column(Float, default=0.0)

    # AI-generated learning
    learnings = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    campaign = relationship("Campaign", back_populates="memory")
