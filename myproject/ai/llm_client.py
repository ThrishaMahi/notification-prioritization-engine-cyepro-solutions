import os, json, asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
client  = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
TIMEOUT = float(os.getenv("AI_TIMEOUT_SECONDS", 2))

SYSTEM_PROMPT = """
You are a Notification Prioritization Engine.
Classify the notification as exactly one of: now, later, never.
- now   = urgent or high-value
- later = useful but not urgent
- never = spam, duplicate, or stale
Respond ONLY with JSON: {"decision": "now|later|never", "reason": "<one sentence>"}
"""

async def ai_classify(event: dict, score: int) -> dict:
    prompt = (
        f"Event type: {event.get('event_type')}\n"
        f"Title: {event.get('title')}\n"
        f"Message: {event.get('message')}\n"
        f"Priority hint: {event.get('priority_hint', 'none')}\n"
        f"Score: {score}\n"
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
