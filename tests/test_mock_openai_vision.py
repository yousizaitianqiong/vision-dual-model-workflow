import json

import pytest
from fastapi.testclient import TestClient

from services.mock_openai_vision_server import app


client = TestClient(app, raise_server_exceptions=False)


def test_models_endpoint():
    response = client.get("/v1/models")

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "mock-vision"


def test_json_chat_completion():
    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "请检查道路画面"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["object"] == "chat.completion"
    assert payload["choices"][0]["message"]["role"] == "assistant"
    assert payload["usage"]["total_tokens"] > 0


def test_sse_chat_completion():
    response = client.post(
        "/v1/chat/completions",
        json={
            "stream": True,
            "messages": [{"role": "user", "content": "请检查安全风险"}],
        },
    )

    assert response.status_code == 200
    assert "data:" in response.text
    assert "data: [DONE]" in response.text


def test_chat_requires_messages():
    response = client.post("/v1/chat/completions", json={})

    assert response.status_code == 422
    assert response.json() == {"error": {"message": "messages 必须是数组"}}


@pytest.mark.parametrize("payload", [None, [], "text", 42, True])
def test_chat_requires_json_object(payload):
    response = client.post(
        "/v1/chat/completions",
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"error": {"message": "请求必须是 JSON 对象"}}


@pytest.mark.parametrize("invalid_message", [None, "text", 42, True, []])
@pytest.mark.parametrize("invalid_first", [False, True])
@pytest.mark.parametrize("stream", [False, True])
def test_chat_requires_object_messages(invalid_message, invalid_first, stream):
    valid_message = {"role": "user", "content": "请检查道路画面"}
    messages = (
        [invalid_message, valid_message]
        if invalid_first
        else [valid_message, invalid_message]
    )

    response = client.post(
        "/v1/chat/completions", json={"messages": messages, "stream": stream}
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"error": {"message": "messages 中的每一项必须是对象"}}


def test_chat_requires_valid_json():
    response = client.post(
        "/v1/chat/completions",
        content="{",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json() == {"error": {"message": "请求必须是 JSON"}}


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请检查合成画面"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "https://example.com/synthetic.png"},
                    },
                ],
            }
        ],
    ],
    ids=["empty", "multimodal"],
)
@pytest.mark.parametrize("stream", [False, True])
def test_chat_accepts_empty_and_multimodal_messages(messages, stream):
    response = client.post(
        "/v1/chat/completions", json={"messages": messages, "stream": stream}
    )

    assert response.status_code == 200
    if stream:
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.text.endswith("data: [DONE]\n\n")
    else:
        assert response.headers["content-type"] == "application/json"
        assert response.json()["object"] == "chat.completion"
    if messages:
        assert "请检查合成画面" in response.text
