from typing import TypedDict


class AgentPipelineState(TypedDict):
    run_id: str
    batch_offset: int
    batch_size: int
    decision_method: str        # "rule_based" | "heuristics" | "ml"
    raw_users: list[dict]       # Output of SQL Agent
    scored_users: list[dict]    # Output of Decision Agent
    recommended_users: list[dict]  # Output of Recommendation Agent
    messages: list[dict]        # Output of Message Agent
    current_stage: str          # sql | decision | recommendation | message | done
    errors: list[str]
    # LLM reasoning logs per stage
    sql_agent_log: str
    decision_agent_log: str
    recommendation_agent_log: str
    message_agent_log: str
