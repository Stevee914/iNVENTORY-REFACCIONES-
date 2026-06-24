"""
Capa interna de proveedor LLM — contrato común.

Define el formato neutral de mensajes y la respuesta normalizada que todo
proveedor (Claude, Ollama, ...) debe producir. El router del chatbot y el
loop agéntico (service.py) trabajan SOLO contra este contrato, nunca contra
el SDK de un proveedor concreto.

Formato neutral de mensajes (lista de dicts):
  - {"role": "user"|"assistant", "content": str}
  - turno assistant con tool calls:
      {"role": "assistant", "content": str,
       "tool_calls": [{"id": str, "name": str, "input": dict}, ...]}
  - resultado de herramienta:
      {"role": "tool", "tool_call_id": str, "name": str, "content": str}

Las definiciones de tools se pasan en formato Anthropic (name / description /
input_schema). Cada proveedor las traduce a su formato nativo si hace falta.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class LLMProviderError(Exception):
    """Error de proveedor presentable al usuario (sin stack trace crudo)."""


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"   # "end_turn" | "tool_use"


class LLMProvider(ABC):
    """Contrato que implementan claude_provider y ollama_provider."""

    name: str = "base"
    model: str = ""

    @abstractmethod
    def chat(self, messages: list[dict], system: str, tools: list[dict]) -> LLMResponse:
        """
        Ejecuta UN turno del modelo.

        messages : historial en formato neutral
        system   : system prompt
        tools    : definiciones de tools en formato Anthropic

        Devuelve LLMResponse normalizado. Debe lanzar LLMProviderError ante
        fallos esperables (sin API key, servicio caído, timeout).
        """
        raise NotImplementedError
