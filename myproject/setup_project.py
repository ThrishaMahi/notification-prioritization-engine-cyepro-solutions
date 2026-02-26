import os

files = {

".env.example": """DATABASE_URL=postgresql://user:password@localhost:5432/notifications
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=your_openai_key_here
AI_TIMEOUT_SECONDS=2
APP_PORT=8000
""",

"requirements.txt": """fastapi==0.111.0
uvicorn==0.29.0
pydantic==2.7.0
sqlalchemy==2.0.30
psycopg2-binary==2.9.9
redis==5.0.4
openai==1.30.0
python-dotenv==1.0.1
httpx==0.27.0
pytest==8.2.0
pytest-asyncio==0.23.7
PyYAML==6.0.1
""",

"config/rules.yaml": """fatigue:
  max_per_hour: 5
  max_per_day: 20
  cooldown_seconds: 300

deduplication:
  exact_ttl_seconds: 3600
  near_duplicate_threshold: 0.85

priority_map:
  critical: 100
  high: 75
  medium: 50
  low: 25
  promotional: 10

event_rules:
  - event_type: "payment_failed"
    action: "now"
    reason: "Always send payment failures immediately"

  - event_type: "promo_offer"
    action: "later"
    send_at: "09:00"
    reason: "Promotional content batched to morning"

  - event_type: "system_ping"
    action: "never"
    reason: "Internal pings suppressed from user notifications"

quiet_hours:
  enabled: true
  start: "22:00"
  end: "08:00"
  override_for: ["critical"]
""",

"db/schema.sql": """CREATE TABLE IF NOT EXISTS notification_events (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    title         TEXT,
    message       TEXT,
    source        TEXT,
    priority_hint TEXT,
    channel       TEXT,
    dedupe_key    TEXT,
    expires_at    TIMESTAMP,
    metadata      JSONB DEFAULT '{}',
    timestamp     TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_events_user   ON notification_events(user_id);
CREATE INDEX idx_events_dedupe ON notification_events(dedupe_key);

CREATE TABLE IF NOT EXISTS decision_logs (
    id           TEXT PRIMARY KEY,
    event_id     TEXT NOT NULL,
    user_id      TEXT NOT NULL,
    decision     TEXT NOT NULL,
    reason       TEXT NOT NULL,
    score        FLOAT DEFAULT 0,
    rule_matched TEXT,
    send_at      TIMESTAMP,
    ai_used      TEXT DEFAULT 'yes',
    created_at   TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_logs_event ON decision_logs(event_id);
CREATE INDEX idx_logs_user  ON decision_logs(user_id);

CREATE TABLE IF NOT EXISTS user_history (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    event_type TEXT NOT NULL,
    channel    TEXT,
    sent_at    TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_history_user ON user_history(user_id);

CREATE TABLE IF NOT EXISTS suppression_records (
    id               TEXT PRIMARY KEY,
    event_id         TEXT NOT NULL,
    user_id          TEXT NOT NULL,
    action           TEXT NOT NULL,
    reason           TEXT,
    original_payload JSONB,
    created_at       TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_suppression_user ON suppression_records(user_id);
""",

"db/__init__.py": "",

"db/models.py": """from sqlalchemy import Column, String, Float, DateTime, JSON, Text
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
""",

"db/cache.py": """import redis
import os
from dotenv import load_dotenv

load_dotenv()

_client = None

def get_redis():
    global _client
    if _client is None:
        _client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
    return _client

def mark_seen(key: str, ttl_seconds: int = 3600) -> bool:
    r = get_redis()
    result = r.set(f"dedupe:{key}", 1, ex=ttl_seconds, nx=True)
    return result is None

def increment_counter(user_id: str, window: str) -> int:
    r = get_redis()
    ttl = 3600 if window == "hour" else 86400
    key = f"freq:{user_id}:{window}"
    count = r.incr(key)
    if count == 1:
        r.expire(key, ttl)
    return count

def get_counter(user_id: str, window: str) -> int:
    r = get_redis()
    val = r.get(f"freq:{user_id}:{window}")
    return int(val) if val else 0

def is_in_cooldown(user_id: str, event_type: str, cooldown_seconds: int) -> bool:
    r = get_redis()
    key = f"cooldown:{user_id}:{event_type}"
    exists = r.exists(key)
    if not exists:
        r.set(key, 1, ex=cooldown_seconds)
    return bool(exists)
""",

"engine/__init__.py": "",

"engine/rules_engine.py": """import yaml
import os
from datetime import datetime
from typing import Optional

RULES_PATH = os.path.join(os.path.dirname(__file__), "../config/rules.yaml")
_rules_cache = None

def load_rules() -> dict:
    global _rules_cache
    with open(RULES_PATH, "r") as f:
        _rules_cache = yaml.safe_load(f)
    return _rules_cache

def get_rules() -> dict:
    if _rules_cache is None:
        return load_rules()
    return _rules_cache

def get_priority_score(priority_hint: Optional[str]) -> int:
    return get_rules()["priority_map"].get(priority_hint or "medium", 50)

def check_event_rule(event_type: str) -> Optional[dict]:
    for rule in get_rules().get("event_rules", []):
        if rule["event_type"] == event_type:
            return rule
    return None

def is_quiet_hours(now: Optional[datetime] = None) -> bool:
    qh = get_rules().get("quiet_hours", {})
    if not qh.get("enabled", False):
        return False
    now = now or datetime.now()
    current = now.strftime("%H:%M")
    start, end = qh["start"], qh["end"]
    if start > end:
        return current >= start or current < end
    return start <= current < end

def quiet_hours_override_types() -> list:
    return get_rules().get("quiet_hours", {}).get("override_for", [])

def get_fatigue_config() -> dict:
    return get_rules().get("fatigue", {})

def get_dedupe_config() -> dict:
    return get_rules().get("deduplication", {})
""",

"engine/duplicate_detector.py": """import hashlib
from db.cache import mark_seen
from engine.rules_engine import get_dedupe_config

def _make_exact_key(event: dict) -> str:
    if event.get("dedupe_key"):
        return f"exact:{event['dedupe_key']}"
    payload = f"{event['user_id']}:{event['event_type']}:{event.get('message', '')}"
    return f"exact:{hashlib.md5(payload.encode()).hexdigest()}"

def _token_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    set_a, set_b = set(a.lower().split()), set(b.lower().split())
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)

def is_exact_duplicate(event: dict) -> bool:
    config = get_dedupe_config()
    return mark_seen(_make_exact_key(event), config.get("exact_ttl_seconds", 3600))

def is_near_duplicate(event: dict, recent_messages: list) -> bool:
    threshold = get_dedupe_config().get("near_duplicate_threshold", 0.85)
    incoming  = event.get("message", "") or event.get("title", "")
    return any(_token_similarity(incoming, p) >= threshold for p in recent_messages)
""",

"engine/fatigue_checker.py": """from db.cache import get_counter, increment_counter, is_in_cooldown
from engine.rules_engine import get_fatigue_config

class FatigueResult:
    def __init__(self, blocked: bool, reason: str):
        self.blocked = blocked
        self.reason  = reason

def check_fatigue(user_id: str, event_type: str) -> FatigueResult:
    cfg = get_fatigue_config()
    if is_in_cooldown(user_id, event_type, cfg.get("cooldown_seconds", 300)):
        return FatigueResult(True, f"Cooldown active for '{event_type}'.")
    if get_counter(user_id, "hour") >= cfg.get("max_per_hour", 5):
        return FatigueResult(True, f"Hourly cap reached (max {cfg.get('max_per_hour', 5)}).")
    if get_counter(user_id, "day") >= cfg.get("max_per_day", 20):
        return FatigueResult(True, f"Daily cap reached (max {cfg.get('max_per_day', 20)}).")
    return FatigueResult(False, "Within fatigue limits.")

def record_sent(user_id: str):
    increment_counter(user_id, "hour")
    increment_counter(user_id, "day")
""",

"engine/classifier.py": """from datetime import datetime, timezone
from typing import Optional

from engine.rules_engine import (
    get_priority_score, check_event_rule,
    is_quiet_hours, quiet_hours_override_types
)
from engine.duplicate_detector import is_exact_duplicate, is_near_duplicate
from engine.fatigue_checker import check_fatigue, record_sent
from ai.llm_client import ai_classify
from ai.fallback import fallback_classify


async def classify(event: dict, recent_messages: Optional[list] = None) -> dict:
    user_id         = event["user_id"]
    event_type      = event.get("event_type", "")
    recent_messages = recent_messages or []
    score           = get_priority_score(event.get("priority_hint"))

    # 1. Expiry
    if event.get("expires_at"):
        try:
            exp = datetime.fromisoformat(str(event["expires_at"]))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
                return _d("never", "Notification has expired.", score, "expiry_check")
        except Exception:
            pass

    # 2. Hard rule
    rule = check_event_rule(event_type)
    if rule:
        return _d(rule["action"], rule["reason"], score,
                  f"event_rule:{event_type}", send_at=rule.get("send_at"))

    # 3. Exact duplicate
    if is_exact_duplicate(event):
        return _d("never", "Exact duplicate detected.", score, "exact_dedupe")

    # 4. Near-duplicate
    if is_near_duplicate(event, recent_messages):
        return _d("never", "Near-duplicate detected.", score, "near_dedupe")

    # 5. Quiet hours
    if is_quiet_hours():
        if event.get("priority_hint") not in quiet_hours_override_types():
            return _d("later", "Quiet hours — deferred.", score, "quiet_hours")

    # 6. Fatigue
    fatigue = check_fatigue(user_id, event_type)
    if fatigue.blocked:
        if score >= 75:
            return _d("later", f"High priority but fatigue limit hit — deferred.", score, "fatigue_deferred")
        return _d("never", fatigue.reason, score, "fatigue_suppressed")

    # 7. AI (with fallback)
    try:
        result = await ai_classify(event, score)
    except Exception:
        result = fallback_classify(event, score)

    if result["decision"] == "now":
        record_sent(user_id)

    return _d(result["decision"], result["reason"], score, ai_used=result.get("ai_used", "yes"))


def _d(decision, reason, score, rule_matched=None, send_at=None, ai_used="no"):
    return {"decision": decision, "reason": reason, "score": score,
            "rule_matched": rule_matched, "send_at": send_at, "ai_used": ai_used}
""",

"ai/__init__.py": "",

"ai/llm_client.py": """import os, json, asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
client  = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
TIMEOUT = float(os.getenv("AI_TIMEOUT_SECONDS", 2))

SYSTEM_PROMPT = \"\"\"
You are a Notification Prioritization Engine.
Classify the notification as exactly one of: now, later, never.
- now   = urgent or high-value
- later = useful but not urgent
- never = spam, duplicate, or stale
Respond ONLY with JSON: {"decision": "now|later|never", "reason": "<one sentence>"}
\"\"\"

async def ai_classify(event: dict, score: int) -> dict:
    prompt = (
        f"Event type: {event.get('event_type')}\\n"
        f"Title: {event.get('title')}\\n"
        f"Message: {event.get('message')}\\n"
        f"Priority hint: {event.get('priority_hint', 'none')}\\n"
        f"Score: {score}\\n"
        f"Expires at: {event.get('expires_at', 'none')}"
    )
    response = await asyncio.wait_for(
        client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user",   "content": prompt}],
            temperature=0, max_tokens=100,
        ), timeout=TIMEOUT
    )
    result = json.loads(response.choices[0].message.content.strip())
    result["ai_used"] = "yes"
    return result
""",

"ai/fallback.py": """def fallback_classify(event: dict, score: int) -> dict:
    if score >= 75:
        return {"decision": "now",   "reason": f"[Fallback] High priority ({score}).",   "ai_used": "fallback"}
    elif score >= 25:
        return {"decision": "later", "reason": f"[Fallback] Medium priority ({score}).", "ai_used": "fallback"}
    else:
        return {"decision": "never", "reason": f"[Fallback] Low priority ({score}).",    "ai_used": "fallback"}
""",

"api/__init__.py": "",

"api/routes.py": """import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from engine.classifier import classify
from engine.rules_engine import load_rules

router     = APIRouter()
_decisions = {}
_history   = {}

class NotificationEvent(BaseModel):
    user_id:       str
    event_type:    str
    title:         Optional[str] = None
    message:       Optional[str] = None
    source:        Optional[str] = None
    priority_hint: Optional[str] = "medium"
    channel:       Optional[str] = "push"
    dedupe_key:    Optional[str] = None
    expires_at:    Optional[str] = None
    metadata:      Optional[dict] = {}

class DecisionResponse(BaseModel):
    event_id:     str
    decision:     str
    reason:       str
    score:        int
    rule_matched: Optional[str]
    send_at:      Optional[str]
    ai_used:      str

@router.post("/notify", response_model=DecisionResponse, tags=["Core"])
async def submit_notification(event: NotificationEvent):
    event_id   = str(uuid.uuid4())
    event_dict = event.model_dump()
    event_dict["timestamp"] = datetime.utcnow().isoformat()
    recent = [e.get("message", "") for e in _history.get(event.user_id, [])[-20:]]
    result = await classify(event_dict, recent_messages=recent)
    _decisions[event_id] = {"event_id": event_id, "event": event_dict, **result}
    _history.setdefault(event.user_id, []).append(event_dict)
    return DecisionResponse(event_id=event_id, **result)

@router.get("/decision/{event_id}", tags=["Audit"])
async def get_decision(event_id: str):
    record = _decisions.get(event_id)
    if not record:
        raise HTTPException(404, "Event ID not found.")
    return record

@router.get("/history/{user_id}", tags=["Audit"])
async def get_user_history(user_id: str, limit: int = 50):
    events = _history.get(user_id, [])
    return {"user_id": user_id, "count": len(events), "events": events[-limit:]}

@router.post("/rules/reload", tags=["Admin"])
async def reload_rules():
    try:
        return {"status": "ok", "rules": load_rules()}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/health", tags=["System"])
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
""",

"api/main.py": """import uvicorn
from fastapi import FastAPI
from api.routes import router

app = FastAPI(title="Notification Prioritization Engine", version="1.0.0")
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
""",

"tests/__init__.py": "",

"tests/test_engine.py": """import pytest
from unittest.mock import patch, MagicMock
from engine.duplicate_detector import is_near_duplicate
from engine.fatigue_checker import check_fatigue
from engine.rules_engine import get_priority_score, check_event_rule
from engine.classifier import classify

def test_priority_critical():  assert get_priority_score("critical") == 100
def test_priority_promo():     assert get_priority_score("promotional") == 10
def test_priority_default():   assert get_priority_score(None) == 50

def test_rule_payment():  assert check_event_rule("payment_failed")["action"] == "now"
def test_rule_ping():     assert check_event_rule("system_ping")["action"] == "never"
def test_rule_none():     assert check_event_rule("unknown") is None

def test_near_dup_match():
    assert is_near_duplicate({"message": "Your order shipped", "title": ""},
                              ["Your order has shipped today"]) is True

def test_near_dup_no_match():
    assert is_near_duplicate({"message": "Payment failed", "title": ""},
                              ["Welcome aboard!"]) is False

def test_fatigue_ok():
    with patch("engine.fatigue_checker.get_counter", return_value=0), \\
         patch("engine.fatigue_checker.is_in_cooldown", return_value=False):
        assert check_fatigue("u1", "x").blocked is False

def test_fatigue_hourly():
    with patch("engine.fatigue_checker.get_counter", return_value=10), \\
         patch("engine.fatigue_checker.is_in_cooldown", return_value=False):
        assert check_fatigue("u1", "x").blocked is True

@pytest.mark.asyncio
async def test_payment_now():
    result = await classify({"user_id": "u1", "event_type": "payment_failed",
        "title": "Failed", "message": "...", "priority_hint": "critical", "channel": "push"})
    assert result["decision"] == "now"

@pytest.mark.asyncio
async def test_expired_never():
    result = await classify({"user_id": "u2", "event_type": "sale",
        "title": "Sale", "message": "...", "priority_hint": "high",
        "channel": "push", "expires_at": "2020-01-01T00:00:00"})
    assert result["decision"] == "never"

@pytest.mark.asyncio
async def test_ai_fallback():
    with patch("engine.classifier.ai_classify", side_effect=Exception("timeout")), \\
         patch("engine.classifier.is_exact_duplicate", return_value=False), \\
         patch("engine.classifier.is_near_duplicate",  return_value=False), \\
         patch("engine.classifier.is_quiet_hours",     return_value=False), \\
         patch("engine.classifier.check_fatigue", return_value=MagicMock(blocked=False)):
        result = await classify({"user_id": "u3", "event_type": "msg",
            "title": "Hey", "message": "Hi", "priority_hint": "high", "channel": "push"})
        assert result["ai_used"] == "fallback"
""",

}

# ── Create all files ──────────────────────────────────────────────────────────
for filepath, content in files.items():
    os.makedirs(os.path.dirname(filepath), exist_ok=True) if os.path.dirname(filepath) else None
    with open(filepath, "w") as f:
        f.write(content)
    print(f"✅ Created: {filepath}")

print("\n🎉 Project created! Now run:")
print("   pip install -r requirements.txt")
print("   cp .env.example .env")
print("   python -m api.main")