"""
Proveedor LLM: OpenAI (Chat Completions API).

Envuelve el SDK oficial `openai` detrás del contrato LLMProvider. Traduce el
historial neutral y las definiciones de tools (formato Anthropic) al formato de
OpenAI (function calling) y normaliza la respuesta a LLMResponse.

Config por variables de entorno:
  OPENAI_API_KEY   (requerida)
  OPENAI_MODEL     (default gpt-4o-mini — configurable, NO hardcodear)
  OPENAI_BASE_URL  (opcional; para gateways/compatibles)
"""

import json
import logging

from .base import LLMProvider, LLMResponse, LLMProviderError, ToolCall

logger = logging.getLogger(__name__)

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_OPENAI_MODEL,
        base_url: str | None = None,
        max_tokens: int = 4096,
    ):
        if not api_key:
            raise LLMProviderError(
                "OPENAI_API_KEY no configurada. Agrégala en las variables de "
                "entorno o cambia LLM_PROVIDER."
            )
        # Import diferido: el SDK solo se requiere si se usa este provider.
        try:
            from openai import OpenAI
        except ImportError as e:
            raise LLMProviderError(
                "El paquete 'openai' no está instalado. Agrégalo (pip install openai)."
            ) from e
        self.model = model
        self.max_tokens = max_tokens
        self._client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    # ── neutral → OpenAI ──────────────────────────────────────────────────
    @staticmethod
    def _messages_to_native(system: str, messages: list[dict]) -> list[dict]:
        native: list[dict] = []
        if system:
            native.append({"role": "system", "content": system})
        for m in messages:
            role = m.get("role")
            if role == "tool":
                native.append({
                    "role": "tool",
                    "tool_call_id": m.get("tool_call_id"),
                    "content": m.get("content", ""),
                })
            elif role == "assistant" and m.get("tool_calls"):
                native.append({
                    "role": "assistant",
                    "content": m.get("content") or None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc.get("input", {}), ensure_ascii=False),
                            },
                        }
                        for tc in m["tool_calls"]
                    ],
                })
            else:
                native.append({"role": role, "content": m.get("content", "")})
        return native

    @staticmethod
    def _tools_to_native(tools: list[dict]) -> list[dict]:
        # Anthropic (name/description/input_schema) → OpenAI (function/parameters)
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
            for t in tools
        ]

    # ── chat ──────────────────────────────────────────────────────────────
    def chat(self, messages: list[dict], system: str, tools: list[dict]) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "messages": self._messages_to_native(system, messages),
            "max_tokens": self.max_tokens,
        }
        if tools:
            kwargs["tools"] = self._tools_to_native(tools)
            kwargs["tool_choice"] = "auto"

        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as e:
            # openai.AuthenticationError / APIConnectionError / RateLimitError / APIError
            etype = type(e).__name__
            logger.error("OpenAI error (%s): %s", etype, e)
            if "Authentication" in etype:
                raise LLMProviderError("OPENAI_API_KEY inválida o sin permisos.") from e
            if "Connection" in etype:
                raise LLMProviderError("No se pudo conectar con OpenAI (red/proxy).") from e
            if "RateLimit" in etype:
                raise LLMProviderError("OpenAI: límite de uso alcanzado, reintenta luego.") from e
            raise LLMProviderError(f"Error de OpenAI: {e}") from e

        msg = resp.choices[0].message
        text = msg.content or ""

        tool_calls: list[ToolCall] = []
        for tc in (msg.tool_calls or []):
            args = tc.function.arguments
            if isinstance(args, str):
                try:
                    args = json.loads(args) if args else {}
                except (json.JSONDecodeError, ValueError):
                    args = {}
            tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, input=args or {}))

        stop = "tool_use" if tool_calls else "end_turn"
        return LLMResponse(text=text, tool_calls=tool_calls, stop_reason=stop)
