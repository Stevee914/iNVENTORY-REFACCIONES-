"""Capa interna de proveedor LLM (Claude / Ollama) para el chatbot."""

from .base import LLMProvider, LLMProviderError, LLMResponse, ToolCall
from .service import ChatResult, generate_chat_response, get_provider

__all__ = [
    "LLMProvider",
    "LLMProviderError",
    "LLMResponse",
    "ToolCall",
    "ChatResult",
    "generate_chat_response",
    "get_provider",
]
