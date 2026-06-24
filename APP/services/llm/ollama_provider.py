"""
Proveedor LLM: Ollama local (HTTP).

Habla con un servidor Ollama local vía POST /api/chat usando httpx. Traduce el
historial neutral y las definiciones de tools (formato Anthropic) al formato de
Ollama, y normaliza la respuesta a LLMResponse.

Config por variables de entorno:
  OLLAMA_BASE_URL  (default http://localhost:11434)
  OLLAMA_MODEL     (default llama3.1:8b)

Nota: el tool-calling depende del modelo. Modelos como llama3.1 soportan
`tools` en /api/chat; modelos sin soporte simplemente devuelven texto.
"""

import json
import logging

import httpx

from .base import LLMProvider, LLMResponse, LLMProviderError, ToolCall

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    # ── neutral → Ollama ──────────────────────────────────────────────────
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
                    "content": m.get("content", ""),
                    # informativo; Ollama tolera el campo extra
                    "tool_name": m.get("name", ""),
                })
            elif role == "assistant" and m.get("tool_calls"):
                native.append({
                    "role": "assistant",
                    "content": m.get("content", "") or "",
                    "tool_calls": [
                        {"function": {"name": tc["name"], "arguments": tc.get("input", {})}}
                        for tc in m["tool_calls"]
                    ],
                })
            else:
                native.append({"role": role, "content": m.get("content", "")})
        return native

    @staticmethod
    def _tools_to_native(tools: list[dict]) -> list[dict]:
        # Anthropic (name/description/input_schema) → Ollama (function/parameters)
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
        payload = {
            "model": self.model,
            "messages": self._messages_to_native(system, messages),
            "stream": False,
        }
        if tools:
            payload["tools"] = self._tools_to_native(tools)

        url = f"{self.base_url}/api/chat"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(url, json=payload)
                r.raise_for_status()
                data = r.json()
        except httpx.ConnectError as e:
            logger.error("Ollama no disponible en %s: %s", url, e)
            raise LLMProviderError(
                f"No se pudo conectar a Ollama en {self.base_url}. "
                "Verifica que el servicio esté corriendo (ollama serve)."
            ) from e
        except httpx.TimeoutException as e:
            logger.error("Ollama timeout en %s: %s", url, e)
            raise LLMProviderError(
                f"Ollama no respondió a tiempo (>{int(self.timeout)}s). "
                "El modelo puede estar cargando; reintenta."
            ) from e
        except httpx.HTTPStatusError as e:
            detail = e.response.text[:300] if e.response is not None else str(e)
            logger.error("Ollama HTTP %s: %s", e.response.status_code, detail)
            raise LLMProviderError(
                f"Ollama devolvió error HTTP {e.response.status_code}. "
                f"¿Existe el modelo '{self.model}'? (ollama pull {self.model})"
            ) from e
        except Exception as e:
            logger.error("Ollama error inesperado: %s", e)
            raise LLMProviderError("Error inesperado al contactar a Ollama.") from e

        message = data.get("message", {}) or {}
        text = message.get("content", "") or ""

        tool_calls: list[ToolCall] = []
        for i, tc in enumerate(message.get("tool_calls", []) or []):
            fn = tc.get("function", {}) or {}
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, ValueError):
                    args = {}
            # Ollama no entrega id de tool_call; generamos uno estable por turno.
            tool_calls.append(ToolCall(id=f"call_{i}", name=fn.get("name", ""), input=args or {}))

        stop = "tool_use" if tool_calls else "end_turn"
        return LLMResponse(text=text, tool_calls=tool_calls, stop_reason=stop)
