"""
Proveedor LLM: Claude (Anthropic API).

Envuelve el SDK `anthropic` detrás del contrato LLMProvider. Traduce el
historial neutral al formato nativo de Anthropic (bloques tool_use /
tool_result) y normaliza la respuesta de vuelta a LLMResponse.
"""

import logging

import anthropic

from .base import LLMProvider, LLMResponse, LLMProviderError, ToolCall

logger = logging.getLogger(__name__)


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6", max_tokens: int = 4096):
        if not api_key:
            raise LLMProviderError(
                "ANTHROPIC_API_KEY no configurada. Agrégala en las variables de "
                "entorno o cambia LLM_PROVIDER=ollama."
            )
        self.model = model
        self.max_tokens = max_tokens
        self._client = anthropic.Anthropic(api_key=api_key)

    # ── neutral → Anthropic ───────────────────────────────────────────────
    @staticmethod
    def _to_native(messages: list[dict]) -> list[dict]:
        native: list[dict] = []
        pending_tool_results: list[dict] = []

        def flush_tool_results():
            # Anthropic exige todos los tool_result de un turno en UN mensaje user.
            if pending_tool_results:
                native.append({"role": "user", "content": list(pending_tool_results)})
                pending_tool_results.clear()

        for m in messages:
            role = m.get("role")
            if role == "tool":
                pending_tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": m.get("tool_call_id"),
                    "content": m.get("content", ""),
                })
                continue

            flush_tool_results()

            if role == "assistant" and m.get("tool_calls"):
                blocks: list[dict] = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for tc in m["tool_calls"]:
                    blocks.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc.get("input", {}),
                    })
                native.append({"role": "assistant", "content": blocks})
            else:
                native.append({"role": role, "content": m.get("content", "")})

        flush_tool_results()
        return native

    # ── chat ──────────────────────────────────────────────────────────────
    def chat(self, messages: list[dict], system: str, tools: list[dict]) -> LLMResponse:
        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                tools=tools,
                messages=self._to_native(messages),
            )
        except anthropic.APIError as e:
            logger.error("Claude API error: %s", e)
            raise LLMProviderError(f"Error de Anthropic: {e}") from e
        except Exception as e:  # red/timeout u otros
            logger.error("Claude error inesperado: %s", e)
            raise LLMProviderError("No se pudo contactar a Anthropic.") from e

        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        tool_calls = [
            ToolCall(id=b.id, name=b.name, input=b.input)
            for b in resp.content if getattr(b, "type", None) == "tool_use"
        ]
        stop = "tool_use" if tool_calls else "end_turn"
        return LLMResponse(text=text, tool_calls=tool_calls, stop_reason=stop)
