"""Provider adapter contract.

A provider turns a provider-neutral ``PromptSpecification`` into its own request
format and – only if it supports API generation – executes that request after the
user has explicitly confirmed it. Adapters never decide on their own to spend money.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.models import GeneratedPrompt


class ProviderError(Exception):
    """A provider call failed. ``message`` is user-facing (Finnish)."""

    def __init__(self, message: str, *, status: int | None = None, detail: str | None = None, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.detail = detail
        self.retryable = retryable


@dataclass
class PreparedRequest:
    """Exactly what would be sent, what leaves the machine, and what it may cost."""

    request: dict[str, Any]
    disclosure: list[str]
    cost_estimate: dict[str, Any]
    provider_model: str | None
    warnings: list[str] = field(default_factory=list)


@dataclass
class GenerationResult:
    audio: bytes
    content_type: str
    file_extension: str
    meta: dict[str, Any] = field(default_factory=dict)


class ProviderAdapter(Protocol):
    id: str
    name: str

    def info(self) -> dict[str, Any]: ...

    def supports_generation(self) -> bool: ...

    def prepare(self, prompt: GeneratedPrompt, options: dict[str, Any]) -> PreparedRequest: ...

    def generate(self, request: dict[str, Any]) -> GenerationResult: ...
