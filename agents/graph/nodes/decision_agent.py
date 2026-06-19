"""
Decision Agent Node
Uses create_react_agent with exactly one scoring tool chosen by the RM.
Filters raw_users down to loan candidates.
"""

import json

from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from agents.graph.state import AgentPipelineState
from agents.tools.heuristic_scoring_tool import heuristic_scoring_tool
from agents.tools.ml_tool import ml_predict_tool
from agents.tools.rule_scoring_tool import rule_scoring_tool

_TOOL_MAP = {
    "rule_based": rule_scoring_tool,
    "heuristics": heuristic_scoring_tool,
    "ml": ml_predict_tool,
}

_METHOD_PROMPTS = {
    "rule_based": (
        "Apply rule-based scoring: check for recent large transactions, regular salary credits, "
        "tenure over 12 months, and no major repayment defaults. "
        "Candidates need to pass at least 2 of 4 rules."
    ),
    "heuristics": (
        "Apply heuristic scoring: check high credit card utilisation (>80%), "
        "clean EMI history (good repayment), and high income (>50k/month). "
        "Candidates need to pass at least 1 heuristic."
    ),
    "ml": (
        "Apply ML model scoring: use the Logistic Regression model to predict "
        "loan conversion probability. Flag customers with probability >= 50%."
    ),
}


def decision_agent_node(state: AgentPipelineState, llm) -> dict:
    """
    LangGraph node: scores raw_users with the RM-selected scoring tool.
    Exactly one tool is used per run based on state['decision_method'].
    Returns updated state keys: scored_users, current_stage, decision_agent_log.
    """
    method = state["decision_method"]
    tool = _TOOL_MAP.get(method, rule_scoring_tool)
    method_hint = _METHOD_PROMPTS.get(method, "")

    agent = create_react_agent(llm, tools=[tool])

    users_payload = json.dumps({"users": state["raw_users"]})

    prompt = (
        f"You are a loan candidate evaluation agent.\n"
        f"Evaluate {len(state['raw_users'])} customers to identify good personal loan candidates.\n"
        f"Scoring method: {method}. {method_hint}\n"
        f"Call the scoring tool with the following customer data and report how many candidates were found.\n\n"
        f"Customer data:\n{users_payload}"
    )

    result = agent.invoke({"messages": [HumanMessage(content=prompt)]})

    # Extract scored candidates from ToolMessage
    scored_users = []
    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    if tool_messages:
        try:
            tool_data = json.loads(tool_messages[0].content)
            scored_users = tool_data.get("candidates", [])
        except (json.JSONDecodeError, AttributeError):
            scored_users = []

    final_message = result["messages"][-1]
    log = getattr(final_message, "content", str(final_message))

    return {
        "scored_users": scored_users,
        "current_stage": "recommendation",
        "decision_agent_log": log,
    }
