from db.cache import get_counter, increment_counter, is_in_cooldown
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
