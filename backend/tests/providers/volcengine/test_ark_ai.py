from __future__ import annotations

import pytest

from blueframe.providers.ai import AiRequest
from blueframe.providers.volcengine.ark_ai import ArkAiProvider, ArkResponseError
from blueframe.providers.volcengine.config import ArkProviderConfig


class FixtureTransport:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.payloads: list[dict] = []

    async def post_responses(self, payload: dict) -> dict:
        self.payloads.append(payload)
        return self.response


def request() -> AiRequest:
    return AiRequest(
        operation="story_analysis",
        input={"transcript": "00:00 主角进入房间"},
        output_schema={
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
            "additionalProperties": False,
        },
    )


@pytest.mark.asyncio
async def test_ark_provider_requests_strict_schema_and_validates_output() -> None:
    transport = FixtureTransport(
        {
            "model": "doubao-test",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": '{"title":"开场"}'}],
                }
            ],
            "usage": {"input_tokens": 11, "output_tokens": 4},
        }
    )
    provider = ArkAiProvider(
        ArkProviderConfig(
            credential_reference="memory:ark:key",
            model="doubao-test",
        ),
        transport,
    )

    result = await provider.execute(request())

    assert result.output == {"title": "开场"}
    assert (result.usage.input_units, result.usage.output_units) == (11, 4)
    payload = transport.payloads[0]
    assert payload["text"]["format"] == {
        "type": "json_schema",
        "name": "story_analysis",
        "schema": request().output_schema,
        "strict": True,
    }
    assert payload["store"] is False
    assert payload["thinking"] == {"type": "disabled"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        {"output": []},
        {"output": [{"type": "message", "content": [{"type": "output_text", "text": "```json\\n{}\\n```"}]}]},
        {"output": [{"type": "message", "content": [{"type": "output_text", "text": "{broken"}]}]},
        {"output": [{"type": "message", "content": [{"type": "output_text", "text": "{}"}]}]},
    ],
)
async def test_ark_provider_rejects_missing_fenced_malformed_or_schema_drift(response) -> None:
    provider = ArkAiProvider(
        ArkProviderConfig(credential_reference="memory:ark:key", model="test"),
        FixtureTransport(response),
    )
    with pytest.raises(ArkResponseError):
        await provider.execute(request())
