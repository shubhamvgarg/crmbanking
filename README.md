# CRM Bank - Agentic AI Powered CRM

CRM Bank is a Django-based Agentic AI CRM for Relationship Managers (RMs). It helps an RM identify high-potential customers, recommend suitable loan products, generate personalized WhatsApp outreach, review every AI output, queue approved messages through RabbitMQ, and send WhatsApp messages using Twilio.

The system uses LangGraph for the multi-agent workflow, LangChain tools for agent capabilities, Groq for LLM reasoning, RabbitMQ for asynchronous message delivery, and Twilio for WhatsApp delivery.

---

## Table of Contents

- [Features](#features)
- [Architecture Diagram](#architecture-diagram)
- [Execution Flow](#execution-flow)
- [Project Structure](#project-structure)
- [Tool Design and Usage](#tool-design-and-usage)
- [Data Model Overview](#data-model-overview)
- [Key Design Decisions](#key-design-decisions)
- [Design Patterns Used](#design-patterns-used)
- [Trade-offs and Limitations](#trade-offs-and-limitations)
- [Setup and Run Instructions](#setup-and-run-instructions)
- [Useful Commands](#useful-commands)
- [Important URLs](#important-urls)

---

## Features

- RM login and session-based access control.
- Customer data layer with customer profile, transaction, credit card, and loan history.
- LangGraph-based agent pipeline:
  - SQL Agent
  - Decision Agent
  - Recommendation Agent
  - Message Agent
- RM-selected decision method:
  - Rule-based
  - Heuristics
  - ML model
- Human-in-the-loop review after every agent stage.
- Live pipeline watch page using Server-Sent Events (SSE).
- Batch processing using `AGENT_BATCH_SIZE`.
- RabbitMQ queue for approved messages.
- Consumer worker for asynchronous delivery.
- Twilio WhatsApp delivery.
- Delivery log with Twilio status sync and webhook support.

---

## Architecture Diagram

```mermaid
flowchart TB
    RM[Relationship Manager]
    UI[Django Web UI]
    AUTH[rm_auth App]
    CUST[customers App]
    AGENTS[agents App]
    GRAPH[LangGraph Pipeline]
    GROQ[Groq LLM API]
    HITL[Human Review UI]
    MQAPP[message_queue App]
    RABBIT[Online RabbitMQ]
    WORKER[run_consumer Worker]
    WAPP[whatsapp App]
    TWILIO[Twilio WhatsApp API]
    DB[(SQLite Database)]

    RM --> UI
    UI --> AUTH
    AUTH --> DB
    UI --> CUST
    CUST --> DB
    UI --> AGENTS
    AGENTS --> GRAPH
    GRAPH --> GROQ
    GRAPH --> CUST
    GRAPH --> HITL
    HITL --> AGENTS
    AGENTS --> MQAPP
    MQAPP --> DB
    MQAPP --> RABBIT
    RABBIT --> WORKER
    WORKER --> WAPP
    WAPP --> TWILIO
    WAPP --> DB
    TWILIO --> WAPP
```

### Deployment View

```mermaid
flowchart LR
    Browser[Browser]
    Django[Django runserver / app server]
    Consumer[Queue Consumer Process]
    DB[(SQLite DB)]
    RabbitMQ[Cloud RabbitMQ]
    Groq[Agents]
    Twilio[Twilio API]

    Browser -->|HTTP + SSE| Django
    Django --> DB
    Django --> Groq
    Django --> RabbitMQ
    Consumer --> RabbitMQ
    Consumer --> Twilio
    Consumer --> DB
    Twilio -->|Webhook optional| Django
```

---

## Execution Flow

### End-to-End Pipeline Flow

```mermaid
sequenceDiagram
    actor RM
    participant UI as Django UI
    participant Agents as Agents Views
    participant Graph as LangGraph
    participant DB as Database
    participant Queue as RabbitMQ
    participant Worker as Consumer
    participant Twilio as Twilio API

    RM->>UI: Login
    UI->>DB: Validate RM session
    RM->>UI: Select decision method and run pipeline
    UI->>Agents: Create AgentRun
    Agents->>Graph: Start stream_run
    Graph->>DB: SQL Agent fetches customer batch
    Graph-->>UI: Pause for SQL review
    RM->>UI: Approve/remove customers
    UI->>Graph: Resume pipeline
    Graph->>Graph: Decision Agent scores users
    Graph-->>UI: Pause for Decision review
    RM->>UI: Approve/remove candidates
    Graph->>Graph: Recommendation Agent maps offers
    Graph-->>UI: Pause for Recommendation review
    RM->>UI: Approve/edit offers
    Graph->>Graph: Message Agent drafts messages
    Graph-->>UI: Pause for Message review
    RM->>UI: Approve/edit messages
    UI->>Queue: Publish approved messages
    Worker->>Queue: Consume message
    Worker->>Twilio: Send WhatsApp
    Twilio-->>UI: Webhook / fallback status sync
```

### Agent State Flow

```mermaid
stateDiagram-v2
    [*] --> SQLAgent
    SQLAgent --> SQLReview: pause before Decision Agent
    SQLReview --> DecisionAgent: RM approves raw users
    DecisionAgent --> DecisionReview: pause before Recommendation Agent
    DecisionReview --> RecommendationAgent: RM approves candidates
    RecommendationAgent --> RecommendationReview: pause before Message Agent
    RecommendationReview --> MessageAgent: RM approves offers
    MessageAgent --> MessageReview: RM reviews message drafts
    MessageReview --> SQLAgent: next batch
    MessageReview --> [*]: all batches completed
```

---

## Project Structure

```text
crmbank/
  crmbank/              # Django settings and root URLs
  rm_auth/              # RM authentication and dashboard
  customers/            # Customer data models, admin, seed command, views
  agents/               # LangGraph pipeline, tools, HITL review, run tracking
  message_queue/        # RabbitMQ producer, consumer, queue models
  whatsapp/             # Twilio service, webhook, delivery log
  templates/            # Shared base layout
  static/               # CSS
  requirements.txt
  .env.example
  manage.py
```

---

## Tool Design and Usage

The `agents/tools/` directory contains LangChain tools used by the agent nodes.

### 1. SQL Query Tool

File:

```text
agents/tools/sql_tool.py
```

Purpose:

- Fetches a batch of customers from the Django ORM.
- Joins profile, transactions, loan history, and credit card data.
- Returns compact JSON for the pipeline.

Used by:

```text
SQL Agent
```

### 2. Rule-Based Scoring Tool

File:

```text
agents/tools/rule_scoring_tool.py
```

Purpose:

- Scores customers using deterministic rules.
- Example rules:
  - recent large transaction
  - salary credited regularly
  - relationship tenure
  - repayment behavior

Used when RM selects:

```text
Rule-Based
```

### 3. Heuristic Scoring Tool

File:

```text
agents/tools/heuristic_scoring_tool.py
```

Purpose:

- Scores customers using business heuristics.
- Example signals:
  - credit card usage
  - clean EMI history
  - high income

Used when RM selects:

```text
Heuristics
```

### 4. ML Prediction Tool

File:

```text
agents/tools/ml_tool.py
```

Purpose:

- Builds a lightweight ML scoring model using customer features.
- Predicts conversion probability.

Used when RM selects:

```text
ML Model
```

### 5. Recommendation Tool

File:

```text
agents/tools/recommendation_tool.py
```

Purpose:

- Maps scored candidates to loan products.
- Uses a loan catalogue with offers such as:
  - Premium Personal Loan
  - Pre-Approved Loan
  - Debt Consolidation Loan
  - Salary Advance Loan

Used by:

```text
Recommendation Agent
```

### 6. Notification Tool

File:

```text
agents/tools/notification_tool.py
```

Purpose:

- Provides a queue publishing interface.
- The current production path publishes approved messages after RM review through `message_queue.rabbitmq`.

Note:

Message publishing intentionally happens after final RM approval, not during draft generation.

---

## Data Model Overview

```mermaid
erDiagram
    RMUser ||--o{ AgentRun : triggers
    AgentRun ||--o{ HumanReview : contains
    AgentRun ||--o{ QueuedMessage : creates
    QueuedMessage ||--o{ DeliveryLog : has
    QueuedMessage ||--o| WhatsAppDelivery : sends

    CustomerProfile ||--o{ TransactionData : has
    CustomerProfile ||--o{ CreditCardTransaction : has
    CustomerProfile ||--|| LoanHistory : has
    CustomerProfile ||--o{ CreditCardHistory : has
```

### Core Runtime Models

| Model | App | Purpose |
|---|---|---|
| `RMUser` | `rm_auth` | Relationship Manager login account |
| `CustomerProfile` | `customers` | Main customer record |
| `AgentRun` | `agents` | One pipeline execution |
| `HumanReview` | `agents` | RM review record for each stage |
| `QueuedMessage` | `message_queue` | Approved message ready for RabbitMQ/Twilio |
| `DeliveryLog` | `message_queue` | Queue publish/consume audit trail |
| `WhatsAppDelivery` | `whatsapp` | Twilio message SID and delivery status |

---

## Key Design Decisions

### 1. Django Modular Monolith

The project uses multiple Django apps inside one codebase instead of microservices.

Why:

- Easier for a demo and academic project.
- Shared database and admin.
- Simpler local setup.
- Still keeps clear module boundaries.

### 2. LangGraph for Agent Orchestration

The pipeline uses LangGraph `StateGraph`.

Why:

- The workflow is stateful.
- Each agent modifies shared state.
- Human review requires pause/resume.
- Streaming support allows live progress UI.

### 3. RM Selects One Decision Strategy

The Decision Agent uses exactly one method per run:

- Rule-based
- Heuristics
- ML

Why:

- Clear auditability.
- RM knows which method generated the candidate list.
- Easier comparison across runs.

### 4. Human-in-the-Loop at Every Stage

The pipeline pauses after each stage.

Why:

- Banking communication needs human approval.
- RMs can remove unsuitable users.
- RMs can edit offers and messages.

### 5. RabbitMQ for Async Delivery

Approved messages are not sent directly from the web request.

Why:

- Avoids blocking the user interface.
- Allows retries and logs.
- Separates approval from delivery.

### 6. Twilio for WhatsApp

Twilio handles WhatsApp delivery.

Why:

- Simple sandbox setup.
- Stable API.
- Delivery status callbacks.

### 7. Fallback Twilio Status Sync

The delivery log syncs pending statuses from Twilio when webhooks are unavailable.

Why:

- Localhost cannot receive public Twilio webhooks unless exposed via a public URL.
- Demo still needs accurate status updates.

---

## Design Patterns Used

| Pattern | Used In | Why |
|---|---|---|
| Pipeline / State Machine | `agents/graph/pipeline.py` | Multi-stage agent workflow |
| Strategy Pattern | `decision_agent.py` | Switch scoring method based on RM choice |
| Producer-Consumer | `message_queue` + RabbitMQ | Async WhatsApp sending |
| Service Layer | `message_queue/rabbitmq.py`, `whatsapp/services.py` | Encapsulates external APIs |
| Decorator Pattern | `rm_auth/decorators.py` | Reusable RM login protection |
| Checkpoint / Saga | LangGraph `MemorySaver` + interrupts | Pause/resume with RM review |
| Webhook Pattern | `whatsapp/views.py` | Async Twilio status updates |
| Context Manager | `rabbitmq_channel()` | Safe RabbitMQ connection lifecycle |

---

## Trade-offs and Limitations

### Trade-offs

| Decision | Benefit | Trade-off |
|---|---|---|
| Django monolith | Simple setup and development | Less independent scaling than microservices |
| SQLite | Easy local demo | Not ideal for production concurrency |
| In-memory LangGraph checkpoint | Simple HITL resume during running server | Checkpoints lost if server restarts |
| Batch processing | Easier review and control | More clicks for large datasets |
| RabbitMQ worker process | Reliable async delivery | Must run consumer separately |
| Twilio Sandbox | Easy demo | Recipient must join sandbox |

### Current Limitations

- `run_consumer` must be started separately from Django.
- Local webhook callbacks need a public URL such as ngrok.
- SQLite should be replaced with PostgreSQL in production.
- The demo has a hardcoded Twilio recipient for safe testing.
- Full automated test coverage is not yet complete.

---

## Setup and Run Instructions

### 1. Create and Activate Virtual Environment

```bash
python -m venv venv
.\venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
copy .env.example .env
```

Update these values:

```env
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Free LLM APIS
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile

# CloudAMQP for rabbitMQ services 
RABBITMQ_URL=amqps://user:password@host/vhost
RABBITMQ_QUEUE=whatsapp.messages
RABBITMQ_EXCHANGE=crm.outreach
RABBITMQ_ROUTING_KEY=whatsapp.messages

TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

# Using Batch of 2 because Currently using Free LLM APIs which cannot handle larger dataset at once 
AGENT_BATCH_SIZE=2
DEFAULT_DECISION_METHOD=rule_based
```

### 4. Run Migrations

```bash
python manage.py migrate
```

### 5. Create Admin User

```bash
python manage.py createsuperuser
```

### 6. Seed Demo Customers

For 10 demo customers:

```bash
python manage.py seed_demo_data --clear --count 10
```

### 7. Start Django Server

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

### 8. Start RabbitMQ Consumer

In a separate terminal:

```bash
python manage.py run_consumer
```

For one-message testing:

```bash
python manage.py run_consumer --once
```

---

## Useful Commands

### Django Checks

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
```

### Data

```bash
python manage.py seed_demo_data --clear --count 10
```

### RabbitMQ

```bash
python manage.py check_rabbitmq
python manage.py run_consumer
python manage.py run_consumer --once
```

### E2E Readiness

```bash
python manage.py validate_e2e
python manage.py validate_e2e --strict
```

---

## Important URLs

| URL | Purpose |
|---|---|
| `/auth/login/` | RM login |
| `/auth/dashboard/` | RM dashboard |
| `/customers/` | Customer list |
| `/agents/` | Agent pipeline dashboard |
| `/agents/run/` | Trigger pipeline |
| `/agents/run/<run_id>/watch/` | Live progress page |
| `/agents/run/<run_id>/review/<stage>/` | Human review page |
| `/agents/run/<run_id>/continue/` | Continue paused run |
| `/agents/runs/` | Run history |
| `/whatsapp/delivery-log/` | WhatsApp delivery log |
| `/whatsapp/webhook/` | Twilio status webhook |
| `/admin/` | Django admin |

---

## Demo Workflow

1. Login as RM.
2. Open Agent Pipeline.
3. Choose decision method.
4. Run pipeline.
5. Watch live agent progress.
6. Review SQL Agent output.
7. Review Decision Agent output.
8. Review Recommendation Agent output.
9. Review/edit Message Agent output.
10. Approved messages are published to RabbitMQ.
11. Run `python manage.py run_consumer --once`.
12. Consumer sends WhatsApp through Twilio.
13. Check `/whatsapp/delivery-log/`.

---

## Final Notes

This project demonstrates an end-to-end Agentic AI CRM workflow:

```text
Customer Data -> AI Agents -> RM Review -> RabbitMQ -> Twilio -> Delivery Log
```

It is designed for demo and learning purposes, while still using production-style patterns such as service layers, queues, webhooks, audit logs, and human-in-the-loop control.
