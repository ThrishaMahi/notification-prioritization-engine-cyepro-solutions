import yaml
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
