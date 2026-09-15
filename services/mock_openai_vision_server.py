"""用于本地联调的 OpenAI 兼容视觉模型 Mock 服务。

它不加载真实模型，只复现工作流需要的 /v1/models 和
/v1/chat/completions 接口，并支持 JSON 与 SSE 两种返回形式。
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Iterator
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse


HOST = os.environ.get("MOCK_MODEL_HOST", "0.0.0.0")
PORT = int(os.environ.get("MOCK_MODEL_PORT", "8001"))
MODEL_NAME = os.environ.get("MOCK_MODEL_NAME", "mock-vision")
MODEL_ROLE = os.environ.get("MOCK_MODEL_ROLE", "screening")

app = FastAPI(title=f"Mock OpenAI Vision Server: {MODEL_NAME}")


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [
                str(item.get("text", ""))
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            return "\n".join(part for part in text_parts if part)
    return ""


def _answer(prompt: str) -> str:
    if MODEL_ROLE == "review":
        return (
            "【复核结论】这是本地 Mock 结果，已收到视觉输入与初筛文本。\n"
            "【复核说明】真实部署时由 Qwen3-VL-8B 独立检查视觉证据，再对照初筛结果。\n"
            "【工程边界】本服务不加载模型权重，不代表真实模型准确率。\n"
            f"【收到的提示词摘要】{prompt[:120]}"
        )
    return (
        "【初筛结论】这是本地 Mock 结果，媒体输入已到达初筛接口。\n"
        "【观察结果】示例服务只验证请求、文件链路和响应协议，不生成真实视觉判断。\n"
        "【待复核疑点】请在真实模型服务中完成视觉证据复核。\n"
        f"【收到的提示词摘要】{prompt[:120]}"
    )


def _usage(prompt: str, answer: str) -> dict[str, int]:
    prompt_tokens = max(1, len(prompt) // 4)
    completion_tokens = max(1, len(answer) // 4)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def _completion_payload(request_id: str, text: str) -> dict[str, Any]:
    return {
        "id": request_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL_NAME,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": _usage("", text),
    }


def _stream_events(
    request_id: str,
    text: str,
) -> Iterator[str]:
    words = text.splitlines(keepends=True)
    for index, part in enumerate(words or [text]):
        payload = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": MODEL_NAME,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant" if index == 0 else None,
                        "content": part,
                    },
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "model": MODEL_NAME, "role": MODEL_ROLE}


@app.get("/v1/models")
def models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_NAME,
                "object": "model",
                "created": 0,
                "owned_by": "local-demo",
            }
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse(status_code=400, content={"error": {"message": "请求必须是 JSON"}})

    messages = payload.get("messages")
    if not isinstance(messages, list):
        return JSONResponse(
            status_code=422,
            content={"error": {"message": "messages 必须是数组"}},
        )

    request_id = f"chatcmpl-{uuid.uuid4().hex}"
    answer = _answer(_last_user_text(messages))
    if payload.get("stream") is True:
        return StreamingResponse(
            _stream_events(request_id, answer),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    result = _completion_payload(request_id, answer)
    result["usage"] = _usage(_last_user_text(messages), answer)
    return JSONResponse(result)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
