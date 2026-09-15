from fastapi.testclient import TestClient

from services.mock_openai_vision_server import app


client = TestClient(app)


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
