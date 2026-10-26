import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from system1.adapters.fakes import FakeLLM
from system1.domain.policy import Policy
from system1.generation.designer import DataDesignerGenerator
from system1.generation.simple import BlindItem, BlindLabels, BucketScore

POLICY = Policy.model_validate(
    {
        "decision_question": "Where does it go?",
        "options": [{"key": "billing", "name": "Billing"}, {"key": "shipping", "name": "Shipping"}],
    }
)


@pytest.fixture
def anthropic_stub():
    """A local Messages API that answers every request with a numbered message."""
    prompts: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            prompts.append(json.dumps(body["messages"]))
            reply = {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": body["model"],
                "content": [{"type": "text", "text": f"My invoice looks wrong, case {len(prompts)}"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
            data = json.dumps(reply).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", prompts
    server.shutdown()


async def test_designer_writes_inputs_and_blind_checks_them(anthropic_stub):
    endpoint, prompts = anthropic_stub
    blind = BlindLabels(
        items=[BlindItem(index=i, scores=[BucketScore(bucket="billing", probability=0.9)]) for i in range(3)]
    )
    generator = DataDesignerGenerator(FakeLLM([(blind, 10)]), "test-key", "stub-model", endpoint=endpoint)

    examples, tokens = await generator.generate(POLICY, "", ["Where is my refund?"], {"billing": 3}, lambda _: None)

    assert [e.label for e in examples] == ["billing"] * 3
    assert all(e.how_sure == pytest.approx(1.0) for e in examples)
    assert len({e.input for e in examples}) == 3
    assert tokens > 10
    # The bucket, the team's samples and a sampled style all reach the model.
    # (The first request is Data Designer's own health check.)
    written = [p for p in prompts if "Target bucket" in p]
    assert len(written) == 3
    assert all("Billing" in p and "Where is my refund?" in p and "typos" in p for p in written)


async def test_designer_needs_a_key():
    generator = DataDesignerGenerator(FakeLLM([]), None, "stub-model")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        await generator.generate(POLICY, "", [], {"billing": 1}, lambda _: None)
