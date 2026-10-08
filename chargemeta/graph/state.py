from typing import Literal, TypedDict

AgentName = Literal["metadata", "governance", "relation", "quality", "finalize"]


class InventoryState(TypedDict, total=False):
    job_id: int
    source_id: int
    objective: str
    plan: list[str]
    completed_agents: list[str]
    current_agent: str
    next_agent: AgentName
    table_count: int
    column_count: int
    relation_count: int
    governance_retry_count: int
    retry_governance: bool
    review_required: bool
    quality_passed: bool
    quality_report: dict
    agent_metrics: dict[str, dict]
    error: str
