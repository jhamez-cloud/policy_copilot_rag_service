"""Exercise the real Gemini SDK over an offline HTTP transport."""

import json
from types import SimpleNamespace

import httpx
import httpx2
import pytest
from pydantic import ValidationError

from policy_copilot_rag_service.rag import generation
from policy_copilot_rag_service.rag.augment import SYSTEM_PROMPT
from policy_copilot_rag_service.settings import Settings


@pytest.fixture
def sdk(monkeypatch):
    settings = SimpleNamespace(
        llm_api_key="test-key",llm_model="test-model",llm_max_tokens=1000,
        llm_timeout_seconds=0.125,
    )
    monkeypatch.setattr(generation,"get_settings",lambda: settings)
    generation._get_client.cache_clear()
    real_client = generation.genai.Client
    clients = []
    requests = []

    def install(handler):
        def transport(request):
            requests.append(request)
            return handler(request)

        def create_client(**kwargs):
            kwargs["http_options"].client_args = {"transport":httpx.MockTransport(transport)}
            client = real_client(**kwargs)
            clients.append(client)
            return client

        monkeypatch.setattr(generation.genai,"Client",create_client)
        return requests

    yield install
    for client in clients:
        client.close()
    generation._get_client.cache_clear()


def response(status,body):
    return httpx.Response(status,json=body)


def test_generation_applies_timeout_and_preserves_prompt(sdk):
    requests = sdk(lambda _: response(200,{
        "candidates":[{"content":{"parts":[{"text":"Grounded answer."}]},"finishReason":"STOP"}],
    }))
    assert generation.generate_answer("Question and excerpts") == "Grounded answer."
    client = generation._get_client()
    assert generation._get_client() is client
    assert len(requests) == 1
    assert requests[0].extensions["timeout"]["read"] == pytest.approx(0.125)
    assert requests[0].headers["X-Server-Timeout"] == "1"
    body = json.loads(requests[0].content)
    assert body["contents"][0]["parts"][0]["text"] == "Question and excerpts"
    assert body["systemInstruction"]["parts"][0]["text"] == SYSTEM_PROMPT
    assert body["generationConfig"]["maxOutputTokens"] == 1000


@pytest.mark.parametrize("status,error_type,detail",[
    (503,generation.GenerationError,"currently unavailable"),
    (429,generation.GenerationError,"quota or rate limit"),
    (403,generation.GenerationError,"API key and model"),
    (404,generation.GenerationError,"API key and model"),
    (504,generation.GenerationTimeout,"timed out"),
])
def test_provider_failures_are_safe_and_are_not_retried(sdk,status,error_type,detail):
    requests = sdk(lambda _: response(status,{
        "error":{"code":status,"message":"private provider diagnostic","status":"ERROR"},
    }))
    with pytest.raises(error_type) as error:
        generation.generate_answer("Question")
    assert len(requests) == 1
    assert detail in error.value.detail
    assert "private provider diagnostic" not in error.value.detail


@pytest.mark.parametrize("error_type",[httpx.ReadTimeout,httpx2.ReadTimeout])
def test_transport_timeouts_are_not_retried(sdk,error_type):
    def timeout(_request):
        raise error_type("Read deadline reached")

    requests = sdk(timeout)
    with pytest.raises(generation.GenerationTimeout):
        generation.generate_answer("Question")
    assert len(requests) == 1


def test_empty_answer_is_a_generation_failure(sdk):
    sdk(lambda _: response(200,{"candidates":[]}))
    with pytest.raises(generation.GenerationError,match="Empty response") as error:
        generation.generate_answer("Question")
    assert "returned no answer" in error.value.detail


@pytest.mark.parametrize("timeout",[0,-1,float("inf"),float("nan")])
def test_settings_reject_unbounded_or_invalid_timeout(timeout):
    with pytest.raises(ValidationError):
        Settings(_env_file=None,neon_database_url="sqlite://",llm_timeout_seconds=timeout)
