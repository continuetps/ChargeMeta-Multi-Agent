import pytest

from chargemeta.agents.supervisor import supervisor_agent


@pytest.mark.asyncio
async def test_supervisor_follows_bounded_plan():
    state = {"job_id": 1, "source_id": 1, "completed_agents": []}
    assert (await supervisor_agent(state))["next_agent"] == "metadata"
    state["completed_agents"] = ["metadata", "governance"]
    assert (await supervisor_agent(state))["next_agent"] == "relation"


@pytest.mark.asyncio
async def test_supervisor_stops_retry_loop():
    state = {
        "job_id": 1,
        "source_id": 1,
        "completed_agents": ["metadata", "relation"],
        "retry_governance": True,
        "governance_retry_count": 1,
    }
    result = await supervisor_agent(state)
    assert result["next_agent"] == "finalize"
    assert result["review_required"] is True
