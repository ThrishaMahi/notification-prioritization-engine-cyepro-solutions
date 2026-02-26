# Notification Prioritization Engine

A smart engine that decides for every incoming notification whether it should be sent **Now**, **Later**, or **Never** — reducing alert fatigue while ensuring critical notifications are never missed.

Built for **Cyepro Solutions – Round 1 AI-Native Solution Crafting Test**

---

## Problem Statement

Users receive too many notifications. Some are repetitive, some arrive at bad times, and some low-value notifications are sent while important ones are missed or delayed.

This system decides for each incoming notification event whether it should be sent **Now**, **Later (deferred)**, or **Never (suppressed)**.

---

## Architecture

```
Incoming Notification Event
          ↓
    ┌─────────────────┐
    │   FastAPI (API) │
    └────────┬────────┘
             ↓
    ┌─────────────────────────────────────┐
    │         7-Step Pipeline             │
    │                                     │
    │  Step 1: Expiry Check               │
    │  Step 2: Hard Rules (rules.yaml)    │
    │  Step 3: Exact Duplicate (Redis)    │
    │  Step 4: Near Duplicate (Jaccard)   │
    │  Step 5: Quiet Hours                │
    │  Step 6: Fatigue Check (Redis)      │
    │  Step 7: AI Classification          │
    │          └── Fallback if AI down    │
    └─────────────────────────────────────┘
             ↓
    Decision: NOW / LATER / NEVER
    + Reason logged for audit
```

---

## Tech Stack

| Layer         | Technology         |
| ------------- | ------------------ |
| API Framework | FastAPI            |
| Language      | Python 3.10        |
| AI Model      | OpenAI GPT-4o-mini |
| Cache         | Redis              |
| Database      | PostgreSQL         |
| Config        | YAML               |
| Testing       | Pytest             |

---

## Project Structure

```
notification-engine/
├── api/
│   ├── main.py          # App entry point
│   └── routes.py        # All endpoints
├── engine/
│   ├── classifier.py    # 7-step decision pipeline
│   ├── duplicate_detector.py
│   ├── fatigue_checker.py
│   └── rules_engine.py
├── ai/
│   ├── llm_client.py    # OpenAI integration
│   └── fallback.py      # Fallback when AI is down
├── db/
│   ├── models.py
│   ├── cache.py         # Redis
│   └── schema.sql
├── config/
│   └── rules.yaml       # Human configurable rules
└── tests/
    └── test_engine.py
```

---

## Quick Start

```bash
# 1.Openfolder
cd myproject
# 2. Install dependencies
pip install -r requirements.txt

# 3. Setup environment
cp .env.example .env

# 4. Start server
python -m api.main

# 5. Open API docs
http://localhost:8000/docs
```

---

## API Endpoints

| Method | Endpoint               | Description                               |
| ------ | ---------------------- | ----------------------------------------- |
| POST   | `/notify`              | Submit notification → get Now/Later/Never |
| GET    | `/decision/{event_id}` | Fetch decision and audit reason           |
| GET    | `/history/{user_id}`   | View user notification history            |
| POST   | `/rules/reload`        | Hot reload rules without restart          |
| GET    | `/health`              | System health check                       |

---

## Decision Pipeline

| Step | Check             | Outcome             |
| ---- | ----------------- | ------------------- |
| 1    | Event expired     | Never               |
| 2    | Hard rule match   | Now / Later / Never |
| 3    | Exact duplicate   | Never               |
| 4    | Near duplicate    | Never               |
| 5    | Quiet hours       | Later               |
| 6    | Fatigue cap       | Never or Later      |
| 7    | AI classification | Now / Later / Never |

---

## Test Results

| Event Type     | Decision   |
| -------------- | ---------- |
| payment_failed | NOW        |
| system_ping    | NEVER      |
| promo_offer    | LATER      |
| expired event  | NEVER      |
| new_message    | AI decides |

---

## Fallback Strategy

If AI is unavailable:

- Score >= 75 → Now
- Score >= 25 → Later
- Score < 25 → Never

---

## Tools Used

- Claude AI for architecture design and code generation
- Manually reviewed and fixed: unicode issues, classifier pipeline, Windows compatibility
