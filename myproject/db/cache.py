import redis
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
