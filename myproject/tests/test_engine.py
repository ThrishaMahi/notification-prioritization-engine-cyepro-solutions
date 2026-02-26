import pytest
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
    with patch("engine.fatigue_checker.get_counter", return_value=0), \
         patch("engine.fatigue_checker.is_in_cooldown", return_value=False):
        assert check_fatigue("u1", "x").blocked is False

def test_fatigue_hourly():
    with patch("engine.fatigue_checker.get_counter", return_value=10), \
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
    with patch("engine.classifier.ai_classify", side_effect=Exception("timeout")), \
         patch("engine.classifier.is_exact_duplicate", return_value=False), \
         patch("engine.classifier.is_near_duplicate",  return_value=False), \
         patch("engine.classifier.is_quiet_hours",     return_value=False), \
         patch("engine.classifier.check_fatigue", return_value=MagicMock(blocked=False)):
        result = await classify({"user_id": "u3", "event_type": "msg",
            "title": "Hey", "message": "Hi", "priority_hint": "high", "channel": "push"})
        assert result["ai_used"] == "fallback"
