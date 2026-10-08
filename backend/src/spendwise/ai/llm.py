"""The one place that talks to a language model.

Everything else depends on the small `LLM` interface below, not on Groq. Tests pass in a fake
model that answers instantly; switching to another provider means writing one new class.
"""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON text, exactly as the model wrote it


@dataclass
class Reply:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLM(Protocol):
    def chat(self, messages: list[dict], tools: list[dict] | None = None, json_mode: bool = False) -> Reply: ...


class GroqLLM:
    """Groq's OpenAI-compatible chat API (free tier at console.groq.com)."""

    def __init__(self, api_key: str, model: str):
        from groq import Groq

        self.client = Groq(api_key=api_key, timeout=30.0, max_retries=2)
        self.model = model

    def chat(self, messages: list[dict], tools: list[dict] | None = None, json_mode: bool = False) -> Reply:
        extra: dict = {}
        if tools:
            extra.update(tools=tools, tool_choice="auto")
        if json_mode:
            extra["response_format"] = {"type": "json_object"}
        r = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            reasoning_effort="low",
            max_completion_tokens=1200,
            **extra,
        )
        msg = r.choices[0].message
        calls = [ToolCall(c.id, c.function.name, c.function.arguments or "{}") for c in (msg.tool_calls or [])]
        return Reply(content=msg.content or "", tool_calls=calls)
