import hashlib
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
