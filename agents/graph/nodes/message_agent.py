"""
Message Generator Agent Node
Uses the LLM to generate personalized WhatsApp messages for each recommended
customer, then calls notification_tool to queue each message.
"""

import json

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from agents.graph.state import AgentPipelineState
from agents.tools.notification_tool import notification_tool

_SYSTEM_PROMPT = """You are a WhatsApp message generation agent for a bank CRM.
Your job is to generate personalized, friendly, and professional loan outreach messages.
For each customer, create a concise message (max 3 sentences) that:
- Addresses them by first name
- Mentions their specific loan offer
- Includes a soft call to action (e.g., "Reply YES to know more")
Keep the tone warm and professional. Do not include special characters or emojis."""


def _generate_messages_batch(llm, recommended_users: list[dict]) -> list[dict]:
    """Generate all messages in one LLM call for efficiency."""
    if not recommended_users:
        return []

    # Build a compact summary of each user for the LLM prompt
    user_summaries = []
    for u in recommended_users:
        offer = u.get("recommended_offer", "Personal Loan")
        offer_details = u.get("offer_details", {})
        user_summaries.append({
            "customer_id": u["customer_id"],
            "first_name": u["name"].split()[0],
            "occupation": u.get("occupation", ""),
            "account_type": u.get("account_type", ""),
            "tenure_months": u.get("relationship_tenure_months", 0),
            "offer": offer,
            "amount_range": offer_details.get("amount_range", ""),
            "interest_rate": offer_details.get("interest_rate", ""),
        })

    prompt = (
        f"Generate personalized WhatsApp messages for {len(user_summaries)} bank customers.\n"
        f"Return ONLY a valid JSON array. Each item must have exactly two keys: "
        f'"customer_id" and "message".\n\n'
        f"Customer data:\n{json.dumps(user_summaries, indent=2)}"
    )

    response = llm.invoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])

    content = response.content.strip()

    # Strip markdown code fences if present
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(
            line for line in lines
            if not line.startswith("```")
        ).strip()

    try:
        messages_raw = json.loads(content)
        if not isinstance(messages_raw, list):
            raise ValueError("Expected a JSON array")
        return messages_raw
    except (json.JSONDecodeError, ValueError):
        # Fallback: return a basic message for each user
        return [
            {
                "customer_id": u["customer_id"],
                "message": (
                    f"Hi {u['first_name']}, you are pre-qualified for our {u['offer']}. "
                    f"Reply YES to know more."
                ),
            }
            for u in user_summaries
        ]


def message_agent_node(state: AgentPipelineState, llm) -> dict:
    """
    LangGraph node: generates personalized WhatsApp messages for each recommended
    customer and queues them via notification_tool.
    Returns updated state keys: messages, current_stage, message_agent_log.
    """
    if not state["recommended_users"]:
        return {
            "messages": [],
            "current_stage": "done",
            "message_agent_log": "No recommended customers to generate messages for.",
        }

    # Step 1: LLM generates all messages in one batch call
    message_list_raw = _generate_messages_batch(llm, state["recommended_users"])

    # Build a lookup {customer_id: message_text}
    msg_lookup = {m["customer_id"]: m.get("message", "") for m in message_list_raw}

    # Step 2: Call notification_tool via create_react_agent for each user
    notification_agent = create_react_agent(llm, tools=[notification_tool])

    final_messages = []
    notification_logs = []

    for user in state["recommended_users"]:
        cid = user["customer_id"]
        msg_text = msg_lookup.get(cid, f"Hi, you are pre-qualified for {user.get('recommended_offer', 'a loan')}. Reply YES to know more.")

        # Build queue payload prompt for the notification_tool
        notify_prompt = (
            f"Queue this WhatsApp message using notification_tool.\n"
            f"user={user['name']}, "
            f"whatsapp_number={user.get('whatsapp_number', '')}, "
            f"offer={user.get('recommended_offer', '')}, "
            f"personalize_message={msg_text}"
        )

        result = notification_agent.invoke({"messages": [HumanMessage(content=notify_prompt)]})

        # Extract queued payload from ToolMessage
        tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        queued_payload = {}
        if tool_messages:
            try:
                queued_payload = json.loads(tool_messages[0].content)
            except (json.JSONDecodeError, AttributeError):
                queued_payload = {}

        final_messages.append({
            "customer_id": cid,
            "name": user["name"],
            "whatsapp_number": user.get("whatsapp_number", ""),
            "offer": user.get("recommended_offer", ""),
            "message": msg_text,
            "conversion_score": user.get("conversion_score", 0),
            "scoring_reason": user.get("scoring_reason", ""),
            "queued": queued_payload.get("status") == "queued_stub",
        })

        notification_logs.append(f"{cid}: queued={queued_payload.get('status', 'unknown')}")

    log = f"Generated and queued {len(final_messages)} messages.\n" + "\n".join(notification_logs)

    return {
        "messages": final_messages,
        "current_stage": "done",
        "message_agent_log": log,
    }
