"""Capa interna de proveedor LLM (Claude / Ollama / OpenAI) para el chatbot."""

from .base import LLMProvider, LLMProviderError, LLMResponse, ToolCall
from .claude_provider import ClaudeProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider
from .service import ChatResult, generate_chat_response, get_provider

__all__ = [
    "LLMProvider",
    "LLMProviderError",
    "LLMResponse",
    "ToolCall",
    "ClaudeProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "ChatResult",
    "generate_chat_response",
    "get_provider",
]
