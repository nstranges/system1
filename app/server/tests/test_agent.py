import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from system1.agent.models import AgentTurn, PendingAction
from system1.config import get_settings
from system1.contracts.llm import TextDelta, TurnComplete

FLAGSHIP = "tallyfern-triage"


def tool_turn(name: str, args: dict, tool_id: str = "tu_1") -> list:
    block = {"type": "tool_use", "id": tool_id, "name": name, "input": args}
    return [TurnComplete(content=[block], stop_reason="tool_use", input_tokens=10, output_tokens=5)]


def text_turn(text: str) -> list:
    block = {"type": "text", "text": text}
    return [TextDelta(text), TurnComplete(content=[block], stop_reason="end_turn", input_tokens=10, output_tokens=5)]


def send(client, project_id: str, text: str = "hi") -> list[dict]:
    res = client.post(f"/api/projects/{project_id}/agent/messages", json={"text": text})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    events = []
    for chunk in res.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in chunk.split("\n"))
        data = json.loads(lines["data"])
        assert lines["event"] == data["type"]
        events.append(data)
    return events


def make_project(client) -> str:
    return client.post("/api/projects", json={"name": "P", "template_id": FLAGSHIP}).json()["id"]


def test_agent_set_rules_updates_policy_and_emits_canvas(client_for):
    client = client_for("org_a", llm_script=[])
    project_id = make_project(client)
    rules = client.get(f"/api/projects/{project_id}/policy").json()["policy"]["rules"]
    rules[0]["text"] = "Reworded by the agent."
    client.app.state.providers.llm._script.extend(
        [tool_turn("set_rules", {"rules": rules}), text_turn("Updated the first rule.")]
    )

    events = send(client, project_id, "reword the first rule")

    canvas = [e for e in events if e["type"] == "canvas"]
    assert len(canvas) == 1 and canvas[0]["version"] == 2 and canvas[0]["changed"] == ["rules"]
    assert canvas[0]["policy"]["rules"][0]["text"] == "Reworded by the agent."
    assert any(e["type"] == "text" for e in events) and events[-1]["type"] == "done"
    saved = client.get(f"/api/projects/{project_id}/policy").json()
    assert saved["version"] == 2 and saved["policy"]["rules"][0]["text"] == "Reworded by the agent."

    # The canvas is re-sent after the tool changed it, and history replays for the UI.
    second_call = client.app.state.providers.llm.calls[1]["messages"]
    assert second_call[-1]["role"] == "user"
    assert "version 2" in second_call[-1]["content"][-1]["text"]
    history = client.get(f"/api/projects/{project_id}/agent/history").json()
    assert history[0] == {"type": "user", "text": "reword the first rule"}
    assert any(e["type"] == "canvas" for e in history)


def test_agent_invalid_rules_returns_tool_error_and_keeps_policy(client_for):
    client = client_for("org_a")
    project_id = make_project(client)
    rules = client.get(f"/api/projects/{project_id}/policy").json()["policy"]["rules"]
    rules[0]["label"] = "no_such_option"
    client.app.state.providers.llm._script.extend(
        [tool_turn("set_rules", {"rules": rules}), text_turn("That label doesn't exist.")]
    )

    events = send(client, project_id)

    assert not any(e["type"] == "canvas" for e in events)
    assert any(e["type"] == "tool" and e["status"] == "error" for e in events)
    assert client.get(f"/api/projects/{project_id}/policy").json()["version"] == 1
    result = client.app.state.providers.llm.calls[1]["messages"][-1]["content"][0]
    assert result["type"] == "tool_result" and result["is_error"] is True
    assert "no_such_option" in result["content"]


def test_request_dataset_creates_pending_action_not_job(client_for):
    client = client_for("org_a")
    project_id = make_project(client)
    client.app.state.providers.llm._script.extend(
        [tool_turn("request_dataset", {"count": 40}), text_turn("Please confirm.")]
    )

    events = send(client, project_id)

    confirm = next(e for e in events if e["type"] == "confirm")
    assert confirm["kind"] == "dataset" and confirm["est_cost_usd"] == 40 * get_settings().est_cost_per_example_usd
    with Session(client.app.state.engine) as session:
        actions = session.scalars(select(PendingAction)).all()
        assert [(a.kind, a.status) for a in actions] == [("dataset", "pending")]

    res = client.post(f"/api/projects/{project_id}/actions/{confirm['action_id']}/confirm")
    assert res.status_code == 409 and res.json()["detail"]["code"] == "not_available"
    assert client.post(f"/api/projects/{project_id}/actions/{confirm['action_id']}/cancel").status_code == 200
    with Session(client.app.state.engine) as session:
        assert session.scalars(select(PendingAction.status)).one() == "cancelled"
        assert session.scalars(select(AgentTurn)).all()


def test_budget_exceeded_emits_error_event(client_for, monkeypatch):
    client = client_for("org_a")
    project_id = make_project(client)
    monkeypatch.setattr(get_settings(), "org_daily_token_cap", 0)

    events = send(client, project_id)

    assert [e["type"] for e in events] == ["error", "done"]
    assert "budget" in events[0]["message"]
    assert client.app.state.providers.llm.calls == []


def test_failed_message_leaves_history_valid_for_the_next_one(client_for):
    from system1.contracts.decisions import ProviderError

    class Boom:
        def __iter__(self):
            raise ProviderError("down")

    client = client_for("org_a")
    project_id = make_project(client)
    client.app.state.providers.llm._script.extend([Boom(), text_turn("Back again.")])

    first = send(client, project_id, "one")
    assert [e["type"] for e in first] == ["error", "done"]
    second = send(client, project_id, "two")
    assert second[-1]["type"] == "done" and any(e["type"] == "text" for e in second)

    messages = client.app.state.providers.llm.calls[1]["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
