import uuid
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
