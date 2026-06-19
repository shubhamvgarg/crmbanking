"""
SQL Agent Node
Uses create_react_agent (LangGraph prebuilt) with sql_query_tool.
Fetches a paginated batch of customers from the database.
"""

import json

from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from agents.graph.state import AgentPipelineState
from agents.tools.sql_tool import sql_query_tool


def sql_agent_node(state: AgentPipelineState, llm) -> dict:
    """
    LangGraph node: fetches a customer batch via sql_query_tool.
    Returns updated state keys: raw_users, current_stage, sql_agent_log.
    """
    print("Creating react agent")
    print(llm)
    agent = create_react_agent(llm, tools=[sql_query_tool])

    prompt = (
        f"You are a data retrieval agent for a bank CRM system.\n"
        f"Fetch customer data for processing: batch_offset={state['batch_offset']}, "
        f"batch_size={state['batch_size']}.\n"
        f"Call the sql_query_tool with these exact parameters and confirm how many customers were retrieved."
    )

    result = agent.invoke({"messages": [HumanMessage(content=prompt)]})

    # Extract full user data from the ToolMessage
    raw_users = []
    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    if tool_messages:
        try:
            tool_data = json.loads(tool_messages[0].content)
            raw_users = tool_data.get("users", [])
        except (json.JSONDecodeError, AttributeError):
            raw_users = []

    final_message = result["messages"][-1]
    log = getattr(final_message, "content", str(final_message))

    return {
        "raw_users": raw_users,
        "current_stage": "decision",
        "sql_agent_log": log,
    }
