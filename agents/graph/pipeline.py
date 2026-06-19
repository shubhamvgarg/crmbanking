"""
LangGraph Pipeline
Linear flow (Phase 3 — no HITL interrupts):
  START → sql_agent → decision_agent → recommendation_agent → message_agent → END

HITL interrupt nodes will be inserted between each stage in Phase 4.
"""

import os

from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph

from agents.graph.nodes.decision_agent import decision_agent_node
from agents.graph.nodes.message_agent import message_agent_node
from agents.graph.nodes.recommendation_agent import recommendation_agent_node
from agents.graph.nodes.sql_agent import sql_agent_node
from agents.graph.state import AgentPipelineState


def _get_llm() -> ChatGroq:
    return ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        api_key=os.getenv("GROQ_API_KEY", ""),
        temperature=0,
        streaming=True,   # enables token-by-token SSE events in stream_mode="messages"
    )


def _build_graph() -> StateGraph:
    llm = _get_llm()

    graph = StateGraph(AgentPipelineState)

    # Wrap each node to inject the shared LLM instance
    graph.add_node("sql_agent", lambda state: sql_agent_node(state, llm))
    graph.add_node("decision_agent", lambda state: decision_agent_node(state, llm))
    graph.add_node("recommendation_agent", lambda state: recommendation_agent_node(state, llm))
    graph.add_node("message_agent", lambda state: message_agent_node(state, llm))

    graph.add_edge(START, "sql_agent")
    graph.add_edge("sql_agent", "decision_agent")
    graph.add_edge("decision_agent", "recommendation_agent")
    graph.add_edge("recommendation_agent", "message_agent")
    graph.add_edge("message_agent", END)

    return graph


def get_compiled_pipeline():
    """Return a compiled, runnable LangGraph pipeline."""
    return _build_graph().compile()


def build_initial_state(
    run_id: str,
    batch_offset: int,
    batch_size: int,
    decision_method: str,
) -> AgentPipelineState:
    return AgentPipelineState(
        run_id=run_id,
        batch_offset=batch_offset,
        batch_size=batch_size,
        decision_method=decision_method,
        raw_users=[],
        scored_users=[],
        recommended_users=[],
        messages=[],
        current_stage="sql",
        errors=[],
        sql_agent_log="",
        decision_agent_log="",
        recommendation_agent_log="",
        message_agent_log="",
    )
