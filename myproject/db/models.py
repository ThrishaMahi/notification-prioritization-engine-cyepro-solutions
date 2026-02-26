from sqlalchemy import Column, String, Float, DateTime, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

def gen_id():
    return str(uuid.uuid4())

class NotificationEvent(Base):
    __tablename__ = "notification_events"
    id            = Column(String, primary_key=True, default=gen_id)
    user_id       = Column(String, nullable=False, index=True)
    event_type    = Column(String, nullable=False)
    title         = Column(String)
    message       = Column(Text)
    source        = Column(String)
    priority_hint = Column(String)
    channel       = Column(String)
    dedupe_key    = Column(String, index=True)
    expires_at    = Column(DateTime, nullable=True)
    metadata_     = Column("metadata", JSON, default=dict)
    timestamp     = Column(DateTime, default=datetime.utcnow)

class DecisionLog(Base):
    __tablename__ = "decision_logs"
    id           = Column(String, primary_key=True, default=gen_id)
    event_id     = Column(String, nullable=False, index=True)
    user_id      = Column(String, nullable=False, index=True)
    decision     = Column(String, nullable=False)
    reason       = Column(Text, nullable=False)
    score        = Column(Float, default=0.0)
    rule_matched = Column(String, nullable=True)
    send_at      = Column(DateTime, nullable=True)
    ai_used      = Column(String, default="yes")
    created_at   = Column(DateTime, default=datetime.utcnow)

class UserHistory(Base):
    __tablename__ = "user_history"
    id         = Column(String, primary_key=True, default=gen_id)
    user_id    = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)
    channel    = Column(String)
    sent_at    = Column(DateTime, default=datetime.utcnow)

class SuppressionRecord(Base):
    __tablename__ = "suppression_records"
    id               = Column(String, primary_key=True, default=gen_id)
    event_id         = Column(String, nullable=False)
    user_id          = Column(String, nullable=False, index=True)
    action           = Column(String, nullable=False)
    reason           = Column(Text)
    original_payload = Column(JSON)
    created_at       = Column(DateTime, default=datetime.utcnow)
