# CRM Bank — Agentic AI Relationship Manager Platform

An intelligent CRM system powered by **Agentic AI** to assist Relationship Managers (RMs) in identifying high-potential customers, scoring loan conversion likelihood, recommending products, and generating personalized WhatsApp outreach — with **human-in-the-loop** verification at every stage.

---

## Table of Contents

1. [Objective](#objective)
2. [Use Case](#use-case)
3. [Expected Capabilities](#expected-capabilities)
4. [System Architecture](#system-architecture)
5. [Django Application Structure](#django-application-structure)
6. [Authentication & Authorization](#authentication--authorization)
7. [Agent Pipeline (LangGraph + LangChain)](#agent-pipeline-langgraph--langchain)
8. [Human-in-the-Loop Workflow](#human-in-the-loop-workflow)
9. [Message Queue & WhatsApp Layer](#message-queue--whatsapp-layer)
10. [Database Schema](#database-schema)
11. [Tools & Integrations](#tools--integrations)
12. [Environment Variables](#environment-variables)
13. [Tech Stack](#tech-stack)
14. [Project Setup (Planned)](#project-setup-planned)
15. [Project Flow — Implementation Phases](#project-flow--implementation-phases)
16. [API Endpoints (Planned)](#api-endpoints-planned)
17. [Design Principles](#design-principles)
18. [Future Extensions](#future-extensions)

---

## Objective

Build an **Agentic AI system** that assists a Relationship Manager (RM) in:

- Identifying **high-potential customers** from banking data
- Estimating **likelihood of conversion** for loan products
- Recommending **suitable loan offers**
- Generating **personalized outreach messages** for WhatsApp delivery

The system supports **three decision methods** (rule-based, heuristics, or ML). The RM selects **exactly one method** per pipeline run. A multi-agent orchestration pipeline with RM oversight runs at each batch step.

---

## Use Case

> **RM asks:** *"Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages."*

**End-to-end flow:**

1. RM logs in, selects a **decision method** (Rule-based, Heuristics, or ML), and clicks **"Run Agent Pipeline"**
2. Agents fetch customer data in batches of 100
3. The Decision Agent scores each batch using **only** the method the RM chose
4. Each batch is filtered, recommended, and messaged
5. RM reviews and approves/removes candidates at each agent stage
6. Approved messages are queued and sent via **Twilio WhatsApp**

---

## Expected Capabilities


| Capability                | Description                                                                                    |
| ------------------------- | ---------------------------------------------------------------------------------------------- |
| Data retrieval            | Fetch customer profiles, transactions, credit card history, and loan records from the database |
| High-value identification | Flag loan candidates using the RM-selected method: rule-based, heuristics, or ML (one per run) |
| Conversion estimation     | Score likelihood via the chosen method — rules, heuristics, or Logistic Regression / XGBoost   |
| Product recommendation    | Map customer profile to suitable loan/offer types                                              |
| Personalized outreach     | Generate WhatsApp-ready messages tailored to each customer; delivered via Twilio               |
| Human verification        | RM can review, edit, or remove candidates before the next batch runs                           |


---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Django Web Application                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐   │
│  │  RM Login    │  │  Agents App  │  │  Queue App   │  │  WhatsApp App  │   │
│  │  (Auth/UI)   │  │ (LangGraph)  │  │ (RabbitMQ)   │  │  (Delivery)    │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘   │
│         │                 │                 │                   │           │
│         └─────────────────┴─────────────────┴───────────────────┘           │
│                                    │                                        │
│                          ┌─────────▼─────────┐                              │
│                          │   PostgreSQL /    │                              │
│                          │   SQLite (Demo)   │                              │
│                          └───────────────────┘                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                          ┌──────────▼──────────┐
                          │      RabbitMQ       │
                          │   (Message Queue)   │
                          └──────────┬──────────┘
                                     │
                          ┌──────────▼──────────┐
                          │  Queue Consumer     │
                          │  (Twilio WhatsApp)  │
                          └─────────────────────┘
```

### Agent Pipeline Flow

```
RM selects decision method + Trigger (One Click)
        │
        ▼
┌───────────────────┐
│   1. SQL Agent    │  ← Fetch 2 users → JSON
└─────────┬─────────┘
          │  [Human Review: approve / remove users]
          ▼
┌───────────────────┐
│ 2. Decision Agent │  ← RM-selected method ONLY (rules | heuristics | ML)
└─────────┬─────────┘
          │  [Human Review: approve / remove candidates]
          ▼
┌───────────────────┐
│ 3. Recommend Agent│  ← Map profile → loan/offer type
└─────────┬─────────┘
          │  [Human Review: approve / edit offers]
          ▼
┌───────────────────┐
│ 4. Message Agent  │  ← Generate personalized WhatsApp text
└─────────┬─────────┘
          │  [Human Review: approve / edit messages]
          ▼
┌───────────────────┐
│  Queue Producer   │  → RabbitMQ
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  Queue Consumer   │  → Send via Twilio WhatsApp API
└───────────────────┘
          │
          ▼ (if more users remain)
   Repeat from SQL Agent (next 100 users)
```

---

## Django Application Structure

```
crmbank/
├── manage.py
├── crmbank/                    # Project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── rm_auth/                    # RM Login & credential management
│   ├── models.py               # RMUser, AdminUser
│   ├── views.py
│   ├── urls.py
│   └── templates/
├── agents/                     # All generative AI agents (single app)
│   ├── graph/                  # LangGraph state machine
│   │   ├── state.py            # Shared agent state schema
│   │   ├── sql_agent.py
│   │   ├── decision_agent.py
│   │   ├── recommendation_agent.py
│   │   ├── message_agent.py
│   │   └── pipeline.py         # Full graph orchestration
│   ├── tools/                  # LangChain tools
│   │   ├── sql_tool.py
│   │   ├── rule_scoring_tool.py
│   │   ├── heuristic_scoring_tool.py
│   │   ├── recommendation_tool.py
│   │   ├── notification_tool.py
│   │   └── ml_tool.py
│   ├── models.py               # AgentRun, AgentBatch, HumanReview
│   ├── views.py
│   └── templates/              # Interactive RM dashboard
├── message_queue/              # RabbitMQ producer/consumer
│   ├── producer.py
│   ├── consumer.py
│   ├── models.py               # QueuedMessage, DeliveryLog
│   └── management/commands/
│       └── run_consumer.py
├── whatsapp/                   # WhatsApp delivery via Twilio
│   ├── services.py             # send_whatsapp_message() via Twilio SDK
│   ├── models.py               # WhatsAppDelivery
│   └── views.py                # Twilio status callback webhook
├── customers/                  # Demo customer data models
│   ├── models.py
│   └── management/commands/
│       └── seed_demo_data.py
└── static/ & templates/        # Frontend assets
```

---

## Authentication & Authorization

### RM Login


| Role      | Capabilities                                                                |
| --------- | --------------------------------------------------------------------------- |
| **Admin** | Create RM credentials (User ID + initial password); manage all RMs          |
| **RM**    | Login with User ID + Password; update own password via email + old password |


### Password Update Flow

```
RM → Enter User ID + Old Password + New Password + Email
     → System validates old password
     → Sends confirmation to registered email
     → Password updated
```

### Security Notes

- Passwords stored using Django's `PBKDF2` hasher (default)
- Session-based authentication for the RM dashboard
- Admin panel restricted to `is_staff` / `is_superuser` accounts
- Groq API key and Twilio credentials loaded from environment variables only

---

## Agent Pipeline (LangGraph + LangChain)

All four agents are implemented as **LangGraph nodes** sharing a typed state object. Each agent invokes **LangChain tools** for side effects (DB queries, scoring, queueing). The LLM (via **Groq API**) handles reasoning, explanation, and message generation.

### Shared Graph State

```python
class AgentPipelineState(TypedDict):
    batch_offset: int           # Current pagination offset (0, 100, 200, ...)
    batch_size: int             # Fixed at 100
    decision_method: str        # "rule_based" | "heuristics" | "ml" — set by RM at run start
    raw_users: list[dict]       # Output of SQL Agent
    scored_users: list[dict]    # Output of Decision Agent
    recommended_users: list[dict]  # Output of Recommendation Agent
    messages: list[dict]        # Output of Message Agent
    human_reviews: dict         # RM approvals/removals per stage
    current_stage: str          # sql | decision | recommendation | message | done
    run_id: str                 # UUID for this pipeline run
    errors: list[str]
```

---

### Agent 1 — SQL Agent

**Purpose:** Fetch customer data from the database and serialize to JSON.


| Property   | Value                                                                               |
| ---------- | ----------------------------------------------------------------------------------- |
| Batch size | 100 users per fetch                                                                 |
| Tool       | `sql_query_tool` — executes parameterized SQL against customer/transaction tables   |
| Output     | List of user JSON objects with profile, transactions, credit card, and loan history |


**Sample output:**

```json
[
  {
    "customer_id": "CUST001",
    "name": "Rajesh Kumar",
    "age": 34,
    "occupation": "Software Engineer",
    "salary": 85000,
    "account_type": "Premium",
    "relationship_tenure_months": 18,
    "existing_products": ["Savings", "Credit Card"],
    "transactions": { "..." : "..." },
    "credit_cards": [ { "..." : "..." } ],
    "loan_history": { "..." : "..." }
  }
]
```

---

### Agent 2 — Decision Making Agent

**Purpose:** Evaluate each user and decide if they are a good loan candidate using **one scoring method chosen by the RM** before the pipeline starts.

The Decision Agent does **not** combine methods. It invokes exactly one tool path based on `decision_method` in graph state.

#### RM Decision Method Selection

Before triggering the pipeline, the RM selects **one** method on the dashboard:


| UI Option  | `decision_method` value | Tool invoked             |
| ---------- | ----------------------- | ------------------------ |
| Rule-based | `rule_based`            | `rule_scoring_tool`      |
| Heuristics | `heuristics`            | `heuristic_scoring_tool` |
| ML Model   | `ml`                    | `ml_predict_tool`        |


The selected method applies to **every batch** in that pipeline run and cannot be changed mid-run without starting a new run.

#### Method 1 — Rule-Based (Simple)

Used when RM selects **Rule-based**. All rules below are evaluated; users meeting enough criteria are flagged as candidates.


| Rule                   | Condition                              | Signal                  |
| ---------------------- | -------------------------------------- | ----------------------- |
| Recent big purchases   | Large transaction in last 30 days      | High probability        |
| Regular salary credits | Salary credited ≥ 3 consecutive months | Stable → good candidate |
| Relationship duration  | Tenure > 12 months                     | Stable → good candidate |
| Repayment history      | No major defaults on record            | Stable → good candidate |


#### Method 2 — Heuristics (Smart Logic)

Used when RM selects **Heuristics**. Only heuristic logic runs — no rules or ML.


| Heuristic              | Condition                        | Signal           |
| ---------------------- | -------------------------------- | ---------------- |
| High credit card usage | Usage > 80% of limit             | Loan need likely |
| Clean EMI history      | No missed EMIs in last 12 months | Eligible         |


#### Method 3 — ML Model (Advanced)

Used when RM selects **ML Model**. Only the trained model runs — no rules or heuristics.


| Property | Value                                                 |
| -------- | ----------------------------------------------------- |
| Models   | Logistic Regression (baseline) / XGBoost (production) |
| Features | Income, spending pattern, loan history, credit score  |
| Output   | Conversion probability (0.0 – 1.0)                    |


**Tools (mutually exclusive — one per run):**


| Tool                     | When used                         |
| ------------------------ | --------------------------------- |
| `rule_scoring_tool`      | `decision_method == "rule_based"` |
| `heuristic_scoring_tool` | `decision_method == "heuristics"` |
| `ml_predict_tool`        | `decision_method == "ml"`         |


The Decision Agent node reads `decision_method` from state and calls **only** the matching tool. Other scoring tools are not loaded or invoked for that run.

**Output:** Filtered list of candidates with scores, reasons, and the method used (e.g. `"decision_method": "heuristics"`).

---

### Agent 3 — Recommendation Agent

**Purpose:** For each approved candidate, recommend a loan/offer type and attach full user details in JSON.


| Customer Profile                 | Recommended Offer       |
| -------------------------------- | ----------------------- |
| High salary (top quartile)       | Premium Personal Loan   |
| Existing customer, clean history | Pre-approved Loan       |
| Low credit score (< 650)         | Small / Starter Loan    |
| High credit card utilization     | Debt Consolidation Loan |
| Long tenure + stable income      | Loyalty Rate Loan       |


**Tool:** `recommendation_tool` — maps profile signals to product catalog

**Output:**

```json
{
  "customer_id": "CUST001",
  "name": "Rajesh Kumar",
  "conversion_score": 0.82,
  "recommended_offer": "Premium Personal Loan",
  "offer_details": {
    "amount_range": "5L – 15L",
    "interest_rate": "10.5%",
    "tenure_months": 60
  },
  "full_profile": { "...": "..." }
}
```

---

### Agent 4 — Message Generator Agent

**Purpose:** Generate a personalized WhatsApp message for each customer and enqueue it via the notification tool.

**Tool:** `notification_tool` — publishes message payload to RabbitMQ

**Queue payload (producer format):**

```json
{
  "user": "rajesh_kumar",
  "whatsapp_number": "+919876543210",
  "offer": "Premium Personal Loan",
  "personalize_message": "Hi Rajesh, as a valued Premium account holder with 18 months of banking with us, you're pre-qualified for a Premium Personal Loan up to ₹15L at 10.5% p.a. Reply YES to know more!"
}
```

---

## Human-in-the-Loop Workflow

Human-in-the-loop (HITL) is implemented as **interrupt nodes** in the LangGraph pipeline. After each agent completes a batch, the graph pauses and waits for RM action before proceeding.

### RM Dashboard — Before Pipeline Start

Before clicking **Run Agent Pipeline**, the RM must select exactly **one** decision method:


| Option         | Description                                                                   |
| -------------- | ----------------------------------------------------------------------------- |
| **Rule-based** | Simple boolean rules on transactions, salary, tenure, and repayment           |
| **Heuristics** | Smart logic on credit card usage and EMI history                              |
| **ML Model**   | Logistic Regression / XGBoost on income, spending, loan history, credit score |


This selection is stored in `AgentRun.decision_method` and passed into `AgentPipelineState`. The Decision Agent uses **only** that method for the entire run.

### RM Dashboard Actions (per batch, per stage)


| Action                 | Effect                                                                    |
| ---------------------- | ------------------------------------------------------------------------- |
| **Approve All**        | Pass all users to the next agent                                          |
| **Remove User**        | Exclude specific users from the pipeline                                  |
| **Edit**               | Modify offer or message before approval (Recommendation & Message stages) |
| **Approve & Continue** | Resume graph → next agent or next batch                                   |


### Batch Loop

```
Batch 1 (users 1–100):
  SQL Agent → [RM Review] → Decision Agent → [RM Review]
  → Recommendation Agent → [RM Review] → Message Agent → [RM Review]
  → Queue messages

Batch 2 (users 101–200):
  SQL Agent → ... (same flow)

... continues until all users are processed
```

### HumanReview Model (planned)


| Field            | Type        | Description                |
| ---------------- | ----------- | -------------------------- |
| `run_id`         | UUID        | Pipeline run identifier    |
| `stage`          | str         | Agent stage name           |
| `batch_offset`   | int         | Batch start index          |
| `original_users` | JSON        | Agent output before review |
| `approved_users` | JSON        | Users RM approved          |
| `removed_users`  | JSON        | Users RM removed           |
| `reviewed_by`    | FK → RMUser | Reviewing RM               |
| `reviewed_at`    | datetime    | Timestamp                  |


---

## Message Queue & WhatsApp Layer

### RabbitMQ Configuration

RabbitMQ is hosted via an **online managed service** (not run locally). Connection credentials are loaded from `.env` (`RABBITMQ_URL` or individual host/user/password fields).


| Setting        | Value                                                |
| -------------- | ---------------------------------------------------- |
| Broker         | Online RabbitMQ service (CloudAMQP, Amazon MQ, etc.) |
| Exchange       | `crm.outreach` (direct)                              |
| Queue          | `whatsapp.messages`                                  |
| Routing key    | `outreach.whatsapp`                                  |
| Message format | JSON (see producer payload above)                    |
| Durability     | Persistent messages                                  |
| Connection     | TLS/SSL recommended (`amqps://`, port 5671)          |


### Producer (`message_queue` app)

- Called by the Message Generator Agent via `notification_tool`
- Serializes payload and publishes to RabbitMQ
- Logs each enqueued message in `QueuedMessage` model

### Consumer (`message_queue` app)

- Django management command: `python manage.py run_consumer`
- Listens on `whatsapp.messages` queue
- Deserializes payload and calls `whatsapp.services.send_whatsapp_message()`

### WhatsApp Delivery Layer (`whatsapp` app — Twilio)

Outbound messages are sent using the **Twilio WhatsApp API** via the official `twilio` Python SDK.

```python
from twilio.rest import Client

def send_whatsapp_message(user: str, whatsapp_number: str,
                          offer: str, message: str) -> DeliveryResult:
    """
    Sends a WhatsApp message via Twilio.
    Uses TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_WHATSAPP_FROM from .env.
    Logs delivery status to WhatsAppDelivery model.
    """
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    result = client.messages.create(
        body=message,
        from_=settings.TWILIO_WHATSAPP_FROM,   # e.g. whatsapp:+14155238886
        to=f"whatsapp:{whatsapp_number}",       # e.g. whatsapp:+919876543210
    )
```


| Delivery Status | Description                                   |
| --------------- | --------------------------------------------- |
| `queued`        | Message accepted by RabbitMQ queue            |
| `sent`          | Successfully submitted to Twilio API          |
| `failed`        | Delivery failed (retry logic applies)         |
| `delivered`     | Confirmed delivery via Twilio status callback |


**Twilio status callback:** Configure `POST /whatsapp/webhook/` as the Twilio status callback URL to receive delivery updates (`sent`, `delivered`, `failed`, etc.).

---

## Database Schema

### `customers` App — Demo Data Models

#### CustomerProfile


| Field                        | Type           | Description                    |
| ---------------------------- | -------------- | ------------------------------ |
| `customer_id`                | CharField (PK) | Unique customer identifier     |
| `name`                       | CharField      | Full name                      |
| `age`                        | IntegerField   | Age                            |
| `occupation`                 | CharField      | Job title / profession         |
| `salary`                     | DecimalField   | Monthly salary                 |
| `account_type`               | CharField      | e.g. Savings, Premium, Current |
| `relationship_tenure_months` | IntegerField   | Months as bank customer        |
| `existing_products`          | JSONField      | List of active products        |
| `whatsapp_number`            | CharField      | WhatsApp contact number        |
| `email`                      | EmailField     | Contact email                  |


#### TransactionData


| Field                       | Type                 | Description                       |
| --------------------------- | -------------------- | --------------------------------- |
| `customer`                  | FK → CustomerProfile | Customer reference                |
| `total_monthly_credits`     | DecimalField         | Total credits this month          |
| `total_monthly_debits`      | DecimalField         | Total debits this month           |
| `salary_credits`            | DecimalField         | Salary amount credited            |
| `average_balance`           | DecimalField         | Average account balance           |
| `recent_large_transactions` | JSONField            | List of large recent transactions |
| `month`                     | DateField            | Reference month                   |


#### CreditCardTransaction


| Field                       | Type                 | Description               |
| --------------------------- | -------------------- | ------------------------- |
| `customer`                  | FK → CustomerProfile | Customer reference        |
| `total_monthly_credit`      | DecimalField         | Total CC spend this month |
| `recent_large_transactions` | JSONField            | Large CC transactions     |
| `month`                     | DateField            | Reference month           |


#### LoanHistory


| Field                   | Type                 | Description             |
| ----------------------- | -------------------- | ----------------------- |
| `customer`              | FK → CustomerProfile | Customer reference      |
| `existing_loans`        | JSONField            | Active loan details     |
| `previous_applications` | JSONField            | Past loan applications  |
| `repayment_behavior`    | CharField            | Good / Bad / Poor       |
| `credit_score`          | IntegerField         | Credit score (nullable) |


#### CreditCardHistory


| Field                  | Type                 | Description                |
| ---------------------- | -------------------- | -------------------------- |
| `customer`             | FK → CustomerProfile | Customer reference         |
| `cd_id`                | CharField            | Credit card identifier     |
| `cd_limit`             | DecimalField         | Credit limit               |
| `cd_usage_above_80pct` | BooleanField         | Usage exceeds 80% of limit |
| `cd_score`             | IntegerField         | Card-specific score        |


> A customer may have **multiple** `CreditCardHistory` records (one per card).

---

### `rm_auth` App

#### RMUser


| Field        | Type               | Description                      |
| ------------ | ------------------ | -------------------------------- |
| `user_id`    | CharField (unique) | Login identifier                 |
| `password`   | CharField (hashed) | Hashed password                  |
| `email`      | EmailField         | For password reset notifications |
| `is_active`  | BooleanField       | Account status                   |
| `created_by` | FK → AdminUser     | Admin who created credentials    |
| `created_at` | DateTimeField      | Account creation timestamp       |


---

### `agents` App

#### AgentRun


| Field                   | Type           | Description                                       |
| ----------------------- | -------------- | ------------------------------------------------- |
| `run_id`                | UUIDField (PK) | Unique run identifier                             |
| `triggered_by`          | FK → RMUser    | RM who started the run                            |
| `decision_method`       | CharField      | `rule_based` / `heuristics` / `ml` — RM selection |
| `status`                | CharField      | running / paused / completed / failed             |
| `current_stage`         | CharField      | Active agent stage                                |
| `batch_offset`          | IntegerField   | Current batch start                               |
| `total_users_processed` | IntegerField   | Running count                                     |
| `started_at`            | DateTimeField  | Run start time                                    |
| `completed_at`          | DateTimeField  | Run end time (nullable)                           |


#### HumanReview

*(See [Human-in-the-Loop Workflow](#human-in-the-loop-workflow) section above)*

---

### `message_queue` App

#### QueuedMessage


| Field        | Type           | Description                |
| ------------ | -------------- | -------------------------- |
| `message_id` | UUIDField (PK) | Unique message ID          |
| `run_id`     | FK → AgentRun  | Associated pipeline run    |
| `payload`    | JSONField      | Full queue payload         |
| `status`     | CharField      | queued / consumed / failed |
| `created_at` | DateTimeField  | Enqueue timestamp          |


#### DeliveryLog


| Field             | Type               | Description               |
| ----------------- | ------------------ | ------------------------- |
| `queued_message`  | FK → QueuedMessage | Source message            |
| `delivery_status` | CharField          | sent / failed / delivered |
| `attempts`        | IntegerField       | Retry count               |
| `last_attempt_at` | DateTimeField      | Last try timestamp        |
| `error_message`   | TextField          | Failure reason (nullable) |


---

## Tools & Integrations

Each agent calls dedicated LangChain tools. Tools are stateless functions registered with the LangGraph node.


| Tool                     | Used By              | Description                                                          |
| ------------------------ | -------------------- | -------------------------------------------------------------------- |
| `sql_query_tool`         | SQL Agent            | Runs paginated SQL query; returns JSON user list                     |
| `rule_scoring_tool`      | Decision Agent       | Rule-based scoring — **only when** `decision_method` is `rule_based` |
| `heuristic_scoring_tool` | Decision Agent       | Heuristic scoring — **only when** `decision_method` is `heuristics`  |
| `ml_predict_tool`        | Decision Agent       | ML model scoring — **only when** `decision_method` is `ml`           |
| `recommendation_tool`    | Recommendation Agent | Maps profile to loan product from catalog                            |
| `notification_tool`      | Message Agent        | Publishes message payload to RabbitMQ                                |
| `human_review_tool`      | All Agents           | Pauses graph; surfaces data to RM dashboard                          |


### Groq LLM Integration

- Provider: **Groq API** (configured via `GROQ_API_KEY` in `.env`)
- Used for: agent reasoning, message personalization, scoring explanations
- Model: `llama-3.3-70b-versatile` (or configurable via env)

### Twilio WhatsApp Integration

- Provider: **Twilio WhatsApp API** (configured via `TWILIO_`* vars in `.env`)
- SDK: `twilio` Python package
- Used for: sending personalized outreach messages consumed from RabbitMQ
- Sandbox: use [Twilio WhatsApp Sandbox](https://www.twilio.com/docs/whatsapp/sandbox) for development; production requires an approved WhatsApp sender

---

## Environment Variables

Create a `.env` file in the project root (never commit this file):

```env
# Django
SECRET_KEY=your-django-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=sqlite:///db.sqlite3

# Groq LLM
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile

# RabbitMQ (online service — e.g. CloudAMQP, Amazon MQ, RabbitMQ Cloud)
# Use the connection details from your provider's dashboard
RABBITMQ_URL=amqps://user:password@your-host.rmq.cloud.amqp.net/vhost
# Or configure individually if your provider does not supply a single URL:
RABBITMQ_HOST=your-host.rmq.cloud.amqp.net
RABBITMQ_PORT=5671
RABBITMQ_USER=your-username
RABBITMQ_PASSWORD=your-password
RABBITMQ_VHOST=your-vhost
RABBITMQ_USE_SSL=True
RABBITMQ_QUEUE=whatsapp.messages
RABBITMQ_EXCHANGE=crm.outreach

# Twilio WhatsApp
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
# Optional: status callback base URL for delivery webhooks
TWILIO_STATUS_CALLBACK_URL=https://your-domain.com/whatsapp/webhook/

# Agent Pipeline
AGENT_BATCH_SIZE=2
ML_MODEL_PATH=models/loan_conversion_model.pkl
DEFAULT_DECISION_METHOD=rule_based
```

---

## Tech Stack


| Layer             | Technology                                                |
| ----------------- | --------------------------------------------------------- |
| Backend framework | Django 5.x                                                |
| AI orchestration  | LangGraph + LangChain                                     |
| LLM provider      | Groq API                                                  |
| Message queue     | RabbitMQ — hosted online service (via `pika` or `celery`) |
| Database          | PostgreSQL (production) / SQLite (demo)                   |
| ML                | scikit-learn (Logistic Regression), XGBoost               |
| Frontend          | Django Templates + HTMX / Alpine.js (interactive UI)      |
| WhatsApp          | Twilio WhatsApp API                                       |
| Environment       | python-dotenv                                             |


---

## Project Setup (Planned)

### Prerequisites

- Python 3.11+
- An account with an **online RabbitMQ service** (e.g. [CloudAMQP](https://www.cloudamqp.com/), [Amazon MQ](https://aws.amazon.com/amazon-mq/), or [RabbitMQ Cloud](https://www.rabbitmq.com/cloud))
- A Groq API key
- A [Twilio](https://www.twilio.com/) account with WhatsApp enabled (Sandbox for dev)
- No local Docker setup required for RabbitMQ

### 1. Provision online RabbitMQ

1. Sign up with your chosen RabbitMQ provider and create a new instance/plan (a free tier is sufficient for development).
2. From the provider dashboard, copy your **AMQP connection URL** (or host, port, username, password, and vhost separately).
3. Note whether the connection uses **TLS/SSL** (most cloud providers use port `5671` with `amqps://`).

### 2. Local setup

```bash
# Clone and enter project
git clone <repo-url>
cd crmbank

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — paste your Groq API key, online RabbitMQ credentials, and Twilio keys
```

Add your RabbitMQ credentials to `.env`:

```env
RABBITMQ_URL=amqps://user:password@your-host.rmq.cloud.amqp.net/vhost
RABBITMQ_QUEUE=whatsapp.messages
RABBITMQ_EXCHANGE=crm.outreach

TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
```

### 3. Initialize database and admin

```bash
python manage.py migrate
python manage.py seed_demo_data
python manage.py createsuperuser
```

### 4. Configure Twilio WhatsApp

1. In the [Twilio Console](https://console.twilio.com/), note your **Account SID** and **Auth Token**.
2. Enable the **WhatsApp Sandbox** (development) or register a production WhatsApp sender.
3. Add credentials to `.env` (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`).
4. For sandbox testing, join the sandbox from your phone using the code Twilio provides.

### 5. Verify RabbitMQ connection

Before starting the app, confirm Django can reach your online RabbitMQ instance:

```bash
python manage.py check_rabbitmq
```

This command (planned) will test the connection using credentials from `.env` and report success or failure.

### 6. Run the application

```bash
# Terminal 1 — Django development server
python manage.py runserver

# Terminal 2 — Queue consumer (connects to online RabbitMQ)
python manage.py run_consumer
```

Access the RM dashboard at: `http://localhost:8000/`

> **Note:** RabbitMQ runs entirely on your cloud provider — no local broker or Docker container is needed. Ensure your firewall/network allows outbound connections to your provider's host and port (typically `5671` for TLS).

---

## Project Flow — Implementation Phases

Build the project incrementally. Each phase delivers a testable milestone before moving to the next. Do not skip phases — later phases depend on earlier ones.

```
Phase 0          Phase 1           Phase 2              Phase 3
Foundation  ──►  RM Auth      ──►  Customer Data   ──►  Agent Pipeline
                     │                  │                      │
                     └──────────────────┴──────────────────────┘
                                              │
Phase 4          Phase 5           Phase 6              Phase 7
HITL Dashboard ──► Message Queue ──► Twilio WhatsApp ──► E2E & Polish
```

---

### Phase 0 — Project Foundation

**Goal:** Bootstrap the Django project and shared configuration.

**Deliverables:**

- [ ] Initialize Django project (`crmbank`) and virtual environment
- [ ] Create `requirements.txt` (Django, LangGraph, LangChain, Groq, pika, twilio, python-dotenv, scikit-learn, xgboost)
- [ ] Configure `settings.py` — apps list, static files, templates, `.env` loading
- [ ] Add `.env.example` with all documented environment variables
- [ ] Base URL routing and project-level templates/layout
- [ ] SQLite database for local development

**Exit criteria:** `python manage.py runserver` starts without errors; `.env` loads correctly.

---

### Phase 1 — RM Auth Module (`rm_auth`)

**Goal:** Relationship Managers can log in, change passwords, and Admins can create RM accounts.

**Deliverables:**

- [ ] Create `rm_auth` Django app
- [ ] `RMUser` model (user_id, hashed password, email, is_active, created_by, created_at)
- [ ] RM login page — User ID + password only
- [ ] Session-based authentication and login-required decorators
- [ ] Password update flow — old password + new password + email verification
- [ ] Admin interface to generate RM credentials (Admin-only)
- [ ] Login / logout / change-password views and templates
- [ ] Redirect authenticated RM to dashboard placeholder

**Exit criteria:** Admin creates an RM account; RM logs in, changes password, and logs out successfully.

---

### Phase 2 — Customer Data Layer (`customers`)

**Goal:** Store demo banking data that agents will query in later phases.

**Deliverables:**

- [ ] Create `customers` Django app
- [ ] Models: `CustomerProfile`, `TransactionData`, `CreditCardTransaction`, `LoanHistory`, `CreditCardHistory`
- [ ] Django admin registration for all customer models
- [ ] `seed_demo_data` management command — populate realistic demo records (100+ customers)
- [ ] Optional read-only list view to verify seeded data in the browser

**Exit criteria:** `python manage.py seed_demo_data` populates all tables; data visible in admin and queryable via Django ORM.

---

### Phase 3 — Agent Pipeline Core (`agents`)

**Goal:** Implement the four LangGraph agents with Groq LLM and LangChain tools (no HITL or queue yet).

**Deliverables:**

- [ ] Create `agents` Django app
- [ ] `AgentPipelineState` typed state schema (`state.py`)
- [ ] Groq LLM client configuration from `GROQ_API_KEY`
- [ ] **SQL Agent** — `sql_query_tool` fetches 100 users per batch as JSON
- [ ] **Decision Agent** — RM-selected method only:
  - [ ] `rule_scoring_tool` (`decision_method = rule_based`)
  - [ ] `heuristic_scoring_tool` (`decision_method = heuristics`)
  - [ ] `ml_predict_tool` (`decision_method = ml`)
- [ ] **Recommendation Agent** — `recommendation_tool` maps profile → loan offer
- [ ] **Message Generator Agent** — generates personalized message text (no queue yet)
- [ ] LangGraph pipeline (`pipeline.py`) — linear flow: SQL → Decision → Recommendation → Message
- [ ] `AgentRun` model — stores run_id, decision_method, status, batch_offset
- [ ] `POST /agents/run/` endpoint with required `decision_method` body field
- [ ] RM dashboard UI — decision method selector (Rule-based / Heuristics / ML) + **Run Pipeline** button

**Exit criteria:** RM selects a decision method, triggers the pipeline, and sees JSON output from all four agents for one batch of 100 users (logged or displayed on dashboard).

---

### Phase 4 — Human-in-the-Loop Dashboard (`agents` UI + graph interrupts)

**Goal:** RM can review, approve, remove, or edit agent output at every stage before the next batch runs.

**Deliverables:**

- [ ] `HumanReview` model — stores original, approved, and removed users per stage/batch
- [ ] LangGraph **interrupt nodes** after each agent stage
- [ ] RM review UI per stage:
  - [ ] Approve all / remove individual users
  - [ ] Edit offers (Recommendation stage) and messages (Message stage)
- [ ] Batch loop — after RM approves batch N, pipeline resumes from SQL Agent at offset N+100
- [ ] Pipeline status view — current stage, batch offset, decision method, progress
- [ ] `GET /agents/run/<run_id>/review/<stage>/` and `POST .../review/<stage>/` endpoints

**Exit criteria:** RM runs pipeline, reviews output at each of the four agent stages, removes unfit users, and the system processes all customer batches until complete.

---

### Phase 5 — Message Queue Layer (`message_queue`)

**Goal:** Enqueue approved messages to online RabbitMQ; consume and process them asynchronously.

**Deliverables:**

- [x] Create `message_queue` Django app
- [x] Connect to **online RabbitMQ service** via `RABBITMQ_URL` (no Docker)
- [x] `QueuedMessage` and `DeliveryLog` models
- [x] `notification_tool` — producer publishes JSON payload to `whatsapp.messages` queue
- [x] Wire Message Generator Agent to call `notification_tool` after RM approval
- [x] `run_consumer` management command — listens on queue, deserializes payload
- [x] `check_rabbitmq` management command — verify cloud broker connection
- [x] Retry logic and error logging for failed publishes/consumes

**Phase 5 commands:**

```bash
python manage.py check_rabbitmq
python manage.py run_consumer
python manage.py run_consumer --once
```

**Exit criteria:** Approved messages appear in RabbitMQ queue; consumer picks them up and logs processing (WhatsApp send stubbed until Phase 6).

---

### Phase 6 — WhatsApp Delivery via Twilio (`whatsapp`)

**Goal:** Consumer sends real WhatsApp messages through Twilio and tracks delivery status.

**Deliverables:**

- [x] Create `whatsapp` Django app
- [x] `send_whatsapp_message()` service using Twilio Python SDK
- [x] `WhatsAppDelivery` model — message SID, status, timestamps
- [x] Wire queue consumer to call Twilio send function
- [x] `POST /whatsapp/webhook/` — Twilio status callback (sent / delivered / failed)
- [x] `GET /whatsapp/delivery-log/` — RM view of sent messages and statuses
- [x] Twilio Sandbox setup documented and tested

**Phase 6 endpoints and commands:**

```bash
python manage.py run_consumer
python manage.py run_consumer --once
```

- Twilio webhook: `/whatsapp/webhook/`
- RM delivery log: `/whatsapp/delivery-log/`

**Exit criteria:** End-to-end: RM approves a message → queue → consumer → Twilio sends WhatsApp → delivery status recorded via webhook.

---

### Phase 7 — End-to-End Integration & Polish

**Goal:** Production-ready demo with cohesive UI, error handling, and full pipeline validation.

**Deliverables:**

- [x] Unified RM dashboard — login, method selection, pipeline trigger, stage reviews, delivery log
- [x] Frontend polish — interactive review tables, live watch page, clear continue/review actions
- [x] Global error handling — agent failures, RabbitMQ downtime, Twilio API errors surfaced to RM
- [x] Logging and audit trail — AgentRun history, HumanReview records, delivery logs
- [x] Full E2E validation command: customers, agents, HITL, queue, Twilio readiness
- [x] Final README / `.env.example` review against implemented code

**Phase 7 validation command:**

```bash
python manage.py validate_e2e
python manage.py validate_e2e --strict
```

**Exit criteria:** A new RM can log in, run the full pipeline with their chosen decision method, review every batch, and confirm WhatsApp messages were sent — without developer intervention.

---

### Phase Summary

| Phase | Module / App        | Key output                                      |
| ----- | ------------------- | ----------------------------------------------- |
| 0     | Project foundation  | Django project runs; env configured             |
| 1     | `rm_auth`           | RM login, password change, Admin credential mgmt |
| 2     | `customers`         | Demo DB schema + seed data                      |
| 3     | `agents`            | 4 LangGraph agents + decision method selection  |
| 4     | `agents` (HITL)     | RM review UI + batch loop across all users      |
| 5     | `message_queue`     | RabbitMQ producer/consumer (online service)     |
| 6     | `whatsapp`          | Twilio WhatsApp send + delivery tracking        |
| 7     | Integration         | Full E2E pipeline + polished RM dashboard       |

---

## API Endpoints (Planned)

### Authentication (`rm_auth`)


| Method | Endpoint                 | Description                         |
| ------ | ------------------------ | ----------------------------------- |
| POST   | `/auth/login/`           | RM login (user_id + password)       |
| POST   | `/auth/logout/`          | End session                         |
| POST   | `/auth/change-password/` | Update password (email + old + new) |
| POST   | `/admin/rm/create/`      | Admin creates RM credentials        |


### Agent Pipeline (`agents`)


| Method | Endpoint                               | Description                                                  |
| ------ | -------------------------------------- | ------------------------------------------------------------ |
| POST   | `/agents/run/`                         | Trigger pipeline; body includes `decision_method` (required) |
| GET    | `/agents/decision-methods/`            | List available decision methods for RM UI                    |
| GET    | `/agents/run/<run_id>/status/`         | Get current run status (includes `decision_method`)          |
| GET    | `/agents/run/<run_id>/review/<stage>/` | Get batch data for RM review                                 |
| POST   | `/agents/run/<run_id>/review/<stage>/` | Submit RM approval/removals                                  |
| GET    | `/agents/runs/`                        | List past pipeline runs                                      |


**Example — trigger pipeline with RM-selected method:**

```json
POST /agents/run/
{
  "decision_method": "heuristics"
}
```

Valid values: `"rule_based"`, `"heuristics"`, `"ml"`.

### WhatsApp (`whatsapp`)


| Method | Endpoint                  | Description                                 |
| ------ | ------------------------- | ------------------------------------------- |
| GET    | `/whatsapp/delivery-log/` | View delivery history                       |
| POST   | `/whatsapp/webhook/`      | Twilio status callback for delivery updates |


---

## Design Principles

This project is built around five core engineering expectations:


| Principle                         | Implementation                                                                       |
| --------------------------------- | ------------------------------------------------------------------------------------ |
| **Clear task decomposition**      | Four specialized agents, each with a single responsibility                           |
| **Effective tool/API usage**      | LangChain tools for DB, ML, queue, and Twilio side effects; one scoring tool per run |
| **Structured reasoning flow**     | LangGraph state machine with typed state and conditional edges                       |
| **Proper state/context handling** | Shared `AgentPipelineState` passed between all nodes                                 |
| **Modular and extensible design** | Separate Django apps; agents/tools/graph in isolated modules                         |


---

## Future Extensions

- **Real-time dashboard** — WebSocket updates as agents process batches
- **A/B message testing** — Generate multiple message variants; track open/reply rates
- **Additional agents** — KYC verification agent, compliance check agent
- **Multi-RM support** — Assign customer segments to different RMs
- **Analytics module** — Conversion funnel, agent performance metrics
- **Scheduler** — Cron-triggered pipeline runs (e.g. first of every month)
- **Audit trail** — Full log of RM decisions and agent outputs for compliance

---

## License

MIT License — see [LICENSE](LICENSE) for details.