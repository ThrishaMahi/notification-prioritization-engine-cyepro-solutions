def fallback_classify(event: dict, score: int) -> dict:
    if score >= 75:
        return {"decision": "now",   "reason": f"[Fallback] High priority ({score}).",   "ai_used": "fallback"}
    elif score >= 25:
        return {"decision": "later", "reason": f"[Fallback] Medium priority ({score}).", "ai_used": "fallback"}
    else:
        return {"decision": "never", "reason": f"[Fallback] Low priority ({score}).",    "ai_used": "fallback"}
