"""
Servicio LLM — selección de proveedor + loop agéntico de tool-use.

Es la única puerta que usa el router del chatbot. Lee LLM_PROVIDER en runtime
para elegir el proveedor, ejecuta el loop de herramientas de forma agnóstica al
proveedor y devuelve un resultado normalizado.

Variables de entorno:
  LLM_PROVIDER   = claude | ollama   (default: claude — no rompe producción)
  ANTHROPIC_API_KEY                  (Claude)
  OLLAMA_BASE_URL = http://localhost:11434
  OLLAMA_MODEL    = llama3.1:8b
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Callable, Optional

from .base import LLMProvider, LLMProviderError
from .claude_provider import ClaudeProvider
from .ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "claude"


@dataclass
class ChatResult:
    reply: str
    tool_calls: list[dict] = field(default_factory=list)
    pending_action: Optional[dict] = None
    provider: str = ""
    model: str = ""


def get_provider(api_key_override: Optional[str] = None) -> LLMProvider:
    """Instancia el proveedor según LLM_PROVIDER (default claude)."""
    provider = os.environ.get("LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower()

    if provider == "ollama":
        return OllamaProvider(
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"),
        )
    if provider == "claude":
        return ClaudeProvider(
            api_key=api_key_override or os.environ.get("ANTHROPIC_API_KEY", ""),
            model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
        )
    raise LLMProviderError(f"LLM_PROVIDER desconocido: '{provider}'. Usa 'claude' u 'ollama'.")


def generate_chat_response(
    messages: list[dict],
    system: str,
    tools: list[dict],
    tool_runner: Callable[[str, dict], str],
    *,
    max_iters: int = 5,
    pending_tools: tuple[str, ...] = (),
    api_key_override: Optional[str] = None,
) -> ChatResult:
    """
    Ejecuta el chat con loop de herramientas usando el proveedor activo.

    messages      : historial en formato neutral
    system        : system prompt
    tools         : definiciones de tools (formato Anthropic)
    tool_runner   : callable(name, input) -> str (resultado JSON de la tool)
    pending_tools  : nombres de tools que marcan pending_action (confirmación)

    Lanza LLMProviderError ante fallos del proveedor (el router lo traduce a
    un mensaje amable para el frontend).
    """
    provider = get_provider(api_key_override)
    logger.info("Chat LLM provider=%s model=%s", provider.name, provider.model)

    history: list[dict] = list(messages)
    tool_calls_log: list[dict] = []
    pending_action: Optional[dict] = None

    for _ in range(max_iters):
        resp = provider.chat(history, system, tools)

        if not resp.tool_calls:
            return ChatResult(
                reply=resp.text,
                tool_calls=tool_calls_log,
                pending_action=pending_action,
                provider=provider.name,
                model=provider.model,
            )

        # Registrar el turno del assistant con sus tool calls
        history.append({
            "role": "assistant",
            "content": resp.text,
            "tool_calls": [{"id": tc.id, "name": tc.name, "input": tc.input} for tc in resp.tool_calls],
        })

        for tc in resp.tool_calls:
            if tc.name in pending_tools:
                pending_action = {"tool": tc.name, "input": tc.input}
            result = tool_runner(tc.name, tc.input)
            tool_calls_log.append({"tool": tc.name, "input": tc.input})
            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tc.name,
                "content": result,
            })

    return ChatResult(
        reply="Se alcanzó el límite de iteraciones del agente.",
        tool_calls=tool_calls_log,
        pending_action=pending_action,
        provider=provider.name,
        model=provider.model,
    )
