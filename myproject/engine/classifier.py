from datetime import datetime, timezone
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
            return _d("later", "Quiet hours active - deferred.", score, "quiet_hours")

    # 6. Fatigue
    fatigue = check_fatigue(user_id, event_type)
    if fatigue.blocked:
        if score >= 75:
            return _d("later", f"High priority but fatigue limit hit � deferred.", score, "fatigue_deferred")
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
