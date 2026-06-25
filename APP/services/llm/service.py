"""
Servicio LLM — selección de proveedor + loop agéntico de tool-use.

Es la única puerta que usa el router del chatbot. Lee LLM_PROVIDER en runtime
para elegir el proveedor, ejecuta el loop de herramientas de forma agnóstica al
proveedor y devuelve un resultado normalizado.

Variables de entorno:
  LLM_PROVIDER   = claude | ollama | openai   (default: claude — no rompe producción)
  ANTHROPIC_API_KEY                  (Claude)
  OLLAMA_BASE_URL = http://localhost:11434
  OLLAMA_MODEL    = llama3.1:8b
  OPENAI_API_KEY                     (OpenAI)
  OPENAI_MODEL    = gpt-4o-mini      (configurable)
  OPENAI_BASE_URL                    (opcional)
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from .base import LLMProvider, LLMProviderError
from .claude_provider import ClaudeProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider, DEFAULT_OPENAI_MODEL

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "claude"

# Logger de métricas dedicado: emite una línea estructurada por request de chat.
# Self-contained para que sea visible aunque el backend no configure logging.
metrics_logger = logging.getLogger("llm.metrics")
if not metrics_logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s [llm.metrics] %(message)s"))
    metrics_logger.addHandler(_h)
    metrics_logger.setLevel(logging.INFO)
    metrics_logger.propagate = False


def _log_chat_metric(provider: str, model: str, latency_ms: int,
                     tool_calls: int, status: str, error_type: Optional[str]) -> None:
    """Log estructurado por request. NO incluye API keys ni prompts/contenido."""
    metrics_logger.info(json.dumps({
        "event": "chat",
        "provider": provider,
        "model": model,
        "latency_ms": latency_ms,
        "tool_calls": tool_calls,
        "status": status,
        "error_type": error_type,
    }, ensure_ascii=False))


def _summarize_action(tool: str, args: dict) -> str:
    """Resumen legible de una acción mutante propuesta, para confirmación."""
    detalle = ", ".join(f"{k}={v}" for k, v in args.items()) if args else "(sin argumentos)"
    return f"{tool}: {detalle}"


@dataclass
class ChatResult:
    reply: str
    tool_calls: list[dict] = field(default_factory=list)
    pending_action: Optional[dict] = None
    provider: str = ""
    model: str = ""
    latency_ms: int = 0
    tool_call_count: int = 0
    error_type: Optional[str] = None


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
    if provider == "openai":
        return OpenAIProvider(
            api_key=api_key_override or os.environ.get("OPENAI_API_KEY", ""),
            model=os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
            base_url=os.environ.get("OPENAI_BASE_URL") or None,
        )
    raise LLMProviderError(
        f"LLM_PROVIDER desconocido: '{provider}'. Usa 'claude', 'ollama' u 'openai'."
    )


def generate_chat_response(
    messages: list[dict],
    system: str,
    tools: list[dict],
    tool_runner: Callable[[str, dict], str],
    *,
    max_iters: int = 5,
    mutating_tools: tuple[str, ...] = (),
    api_key_override: Optional[str] = None,
) -> ChatResult:
    """
    Ejecuta el chat con loop de herramientas usando el proveedor activo.

    messages      : historial en formato neutral
    system        : system prompt
    tools         : definiciones de tools (formato Anthropic)
    tool_runner   : callable(name, input) -> str (resultado JSON de la tool)
    mutating_tools : tools que NUNCA se ejecutan por iniciativa del modelo; se
                     devuelven como pending_action para confirmación explícita

    Lanza LLMProviderError ante fallos del proveedor (el router lo traduce a
    un mensaje amable para el frontend). En éxito y en error se emite una
    métrica estructurada (provider/model/latency_ms/tool_calls/status).
    """
    t0 = time.perf_counter()
    provider_name, model = "?", "?"
    tool_calls_log: list[dict] = []

    try:
        provider = get_provider(api_key_override)
        provider_name, model = provider.name, provider.model
        logger.info("Chat LLM provider=%s model=%s", provider_name, model)

        history: list[dict] = list(messages)
        pending_action: Optional[dict] = None
        reply = "Se alcanzó el límite de iteraciones del agente."

        for _ in range(max_iters):
            resp = provider.chat(history, system, tools)

            if not resp.tool_calls:
                reply = resp.text
                break

            # Registrar el turno del assistant con sus tool calls
            history.append({
                "role": "assistant",
                "content": resp.text,
                "tool_calls": [{"id": tc.id, "name": tc.name, "input": tc.input} for tc in resp.tool_calls],
            })

            for tc in resp.tool_calls:
                if tc.name in mutating_tools:
                    # Tool mutante: NUNCA se ejecuta por iniciativa del modelo.
                    # Se registra como acción pendiente de confirmación explícita
                    # y se le informa al modelo que NO se aplicó.
                    # Se filtran campos vacíos/None que el modelo pudo rellenar,
                    # para no proponer blanquear datos existentes.
                    propuesta = {k: v for k, v in tc.input.items() if v not in (None, "")}
                    pending_action = {
                        "tool": tc.name,
                        "input": propuesta,
                        "summary": _summarize_action(tc.name, propuesta),
                    }
                    tool_calls_log.append({"tool": tc.name, "input": tc.input})
                    history.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": json.dumps({
                            "status": "requires_confirmation",
                            "message": ("Acción NO ejecutada. Requiere confirmación "
                                        "explícita del usuario antes de aplicarse."),
                        }, ensure_ascii=False),
                    })
                    continue
                result = tool_runner(tc.name, tc.input)
                tool_calls_log.append({"tool": tc.name, "input": tc.input})
                history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": result,
                })
    except LLMProviderError as e:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        _log_chat_metric(provider_name, model, latency_ms, len(tool_calls_log),
                         "error", type(e).__name__)
        raise

    latency_ms = int((time.perf_counter() - t0) * 1000)
    _log_chat_metric(provider_name, model, latency_ms, len(tool_calls_log), "ok", None)
    return ChatResult(
        reply=reply,
        tool_calls=tool_calls_log,
        pending_action=pending_action,
        provider=provider_name,
        model=model,
        latency_ms=latency_ms,
        tool_call_count=len(tool_calls_log),
        error_type=None,
    )
