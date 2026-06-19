"""
Recommendation Agent Node
Uses create_react_agent with recommendation_tool.
Maps each scored candidate to the most suitable loan product.
"""

import json

from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from agents.graph.state import AgentPipelineState
from agents.tools.recommendation_tool import recommendation_tool


def recommendation_agent_node(state: AgentPipelineState, llm) -> dict:
    """
    LangGraph node: maps scored_users to loan products via recommendation_tool.
    Returns updated state keys: recommended_users, current_stage, recommendation_agent_log.
    """
    if not state["scored_users"]:
        return {
            "recommended_users": [],
            "current_stage": "message",
            "recommendation_agent_log": "No scored candidates to recommend loans for.",
        }

    agent = create_react_agent(llm, tools=[recommendation_tool])

    candidates_payload = json.dumps({"candidates": state["scored_users"]})

    prompt = (
        f"You are a loan product recommendation agent.\n"
        f"For each of the {len(state['scored_users'])} scored customers, "
        f"recommend the most suitable loan product from the bank's catalog.\n"
        f"Use the recommendation_tool with the candidate data below, "
        f"then summarize which offers were assigned and why.\n\n"
        f"Candidates:\n{candidates_payload}"
    )

    result = agent.invoke({"messages": [HumanMessage(content=prompt)]})

    recommended_users = []
    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    if tool_messages:
        try:
            tool_data = json.loads(tool_messages[0].content)
            recommended_users = tool_data.get("recommended", [])
        except (json.JSONDecodeError, AttributeError):
            recommended_users = []

    final_message = result["messages"][-1]
    log = getattr(final_message, "content", str(final_message))

    return {
        "recommended_users": recommended_users,
        "current_stage": "message",
        "recommendation_agent_log": log,
    }
