"""
LangGraph Pipeline — Phase 4 (HITL enabled)

Flow with interrupt_before on decision_agent, recommendation_agent, message_agent:
  START → sql_agent → [INTERRUPT] → decision_agent → [INTERRUPT]
        → recommendation_agent → [INTERRUPT] → message_agent → END

After message_agent completes the graph finishes (state.next == []).
The stream_run view detects completion and issues a post-pipeline "message_agent" review.

The MemorySaver checkpointer persists state between the interrupt and resume.
Thread ID format: "{run_id}_{batch_offset}" — unique per run+batch.
"""

import os

from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agents.graph.nodes.decision_agent import decision_agent_node
from agents.graph.nodes.message_agent import message_agent_node
from agents.graph.nodes.recommendation_agent import recommendation_agent_node
from agents.graph.nodes.sql_agent import sql_agent_node
from agents.graph.state import AgentPipelineState

# Module-level singleton — persists across requests while the server is running
_checkpointer = MemorySaver()


def _get_llm() -> ChatGroq:
    print('getting llm')
    return ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        api_key=os.getenv("GROQ_API_KEY", ""),
        temperature=0,
        streaming=True,
    )


def _build_graph() -> StateGraph:
    llm = _get_llm()
    graph = StateGraph(AgentPipelineState)

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
    """
    Returns a compiled pipeline with HITL checkpointing.
    interrupt_before pauses the graph AFTER the preceding node runs,
    giving the RM a chance to review and modify that node's output
    before the next node executes.
    """
    return _build_graph().compile(
        checkpointer=_checkpointer,
        interrupt_before=["decision_agent", "recommendation_agent", "message_agent"],
    )


def get_thread_config(run_id: str, batch_offset: int) -> dict:
    """Return the LangGraph config dict for a specific run+batch."""
    return {"configurable": {"thread_id": f"{run_id}_{batch_offset}"}}


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
