from __future__ import annotations

import json
import re

from jsonschema import ValidationError, validate

from blueframe.domain.common import ProviderUsage
from blueframe.providers.ai import AiRequest, AiResult
from blueframe.providers.volcengine.config import ArkProviderConfig


class ArkResponseError(RuntimeError):
    pass


class ArkAiProvider:
    def __init__(self, config: ArkProviderConfig, transport) -> None:
        self.config = config
        self.transport = transport

    async def execute(self, request: AiRequest) -> AiResult:
        schema_name = re.sub(r"[^a-zA-Z0-9_-]", "_", request.operation)[:64]
        payload = {
            "model": request.model_hint or self.config.model,
            "input": [
                {
                    "role": "user",
                    "content": json.dumps(request.input, ensure_ascii=False),
                }
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": request.output_schema,
                    "strict": True,
                }
            },
            "thinking": {"type": "disabled"},
            "max_output_tokens": self.config.max_output_tokens,
            "store": False,
        }
        response = await self.transport.post_responses(payload)
        output = _extract_output(response)
        try:
            validate(instance=output, schema=request.output_schema)
        except ValidationError as error:
            raise ArkResponseError("Volcengine output does not match the requested schema") from error
        usage = response.get("usage") or {}
        return AiResult(
            provider="volcengine-ark",
            model=str(response.get("model") or payload["model"]),
            usage=ProviderUsage(
                input_units=max(int(usage.get("input_tokens") or 0), 0),
                output_units=max(int(usage.get("output_tokens") or 0), 0),
            ),
            output=output,
        )


def _extract_output(response: dict) -> dict:
    texts = [
        content.get("text")
        for item in response.get("output", [])
        if isinstance(item, dict) and item.get("type") == "message"
        for content in item.get("content", [])
        if isinstance(content, dict) and content.get("type") == "output_text"
    ]
    if len(texts) != 1 or not isinstance(texts[0], str):
        raise ArkResponseError("Volcengine response is missing structured output")
    text = texts[0].strip()
    if text.startswith("```"):
        raise ArkResponseError("Volcengine response contains fenced output")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise ArkResponseError("Volcengine response contains malformed JSON") from error
    if not isinstance(value, dict):
        raise ArkResponseError("Volcengine response must be a JSON object")
    return value
