"""Document analysis using the Anthropic API."""

import logging
import os
from dataclasses import dataclass

import anthropic
import click
from anthropic.types import MessageParam, TextBlock
from opentelemetry import trace

from quill.cache import ResponseCache
from quill.roles import SENIOR_PARTNER, Role

__all__ = ["AnalysisResult", "analyze_document"]

logger = logging.getLogger(__name__)

tracer = trace.get_tracer("quill.analyzer")


@dataclass
class AnalysisResult:
    """Result of a document analysis.

    Attributes:
        text: The analysis text from the model.
        role: The persona used for analysis.
        model: The model identifier.
        input_tokens: Input tokens consumed (zero on cache hit).
        output_tokens: Output tokens consumed (zero on cache hit).
        cache_hit: Whether the result was served from cache.
        truncated: Whether the API response was truncated.
        error: Error message if the analysis failed, None on success.
    """

    text: str
    role: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_hit: bool = False
    truncated: bool = False
    error: str | None = None


def analyze_document(
    text: str,
    role: Role = SENIOR_PARTNER,
    *,
    api_key: str | None = None,
) -> AnalysisResult:
    """Analyze a legal document using the Anthropic API.

    Args:
        text: The document text to analyze.
        role: The role to use for analysis.
        api_key: Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.

    Returns:
        An AnalysisResult with the model's assessment.

    Raises:
        click.ClickException: On missing API key or API errors.
    """
    resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not resolved_key:
        raise click.ClickException(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Get your key at https://console.anthropic.com/"
        )

    cache = ResponseCache()

    with tracer.start_as_current_span(
        "quill.analyze",
        attributes={
            "code.function.name": "quill.analyzer.analyze_document",
            "quill.role": role.name,
            "quill.model": role.model,
        },
    ) as span:
        response = cache.get(role.model, role.system_prompt, text)
        cache_hit = response is not None
        span.set_attribute("quill.cache.hit", cache_hit)

        if response is None:
            try:
                client = anthropic.Anthropic(api_key=resolved_key)
                messages: list[MessageParam] = [{"role": "user", "content": text}]
                response = client.messages.create(
                    model=role.model,
                    max_tokens=4096,
                    system=role.system_prompt,
                    messages=messages,
                )
            except anthropic.AuthenticationError:
                raise click.ClickException(
                    "Invalid ANTHROPIC_API_KEY. Check your API key and try again."
                ) from None
            except anthropic.RateLimitError:
                raise click.ClickException(
                    "Rate limited by the Anthropic API. Please wait and try again."
                ) from None
            except anthropic.APIConnectionError:
                raise click.ClickException(
                    "Could not connect to the Anthropic API. "
                    "Check your network connection."
                ) from None
            except anthropic.APIError as e:
                raise click.ClickException(f"Anthropic API error: {e}") from None

            try:
                cache.put(role.model, role.system_prompt, text, response)
            except OSError:
                logger.warning("Failed to write cache, continuing with result")

        truncated = response.stop_reason == "max_tokens"
        if truncated:
            logger.warning("Response was truncated (max_tokens reached)")

        content_block = next(
            (b for b in response.content if isinstance(b, TextBlock)), None
        )
        if content_block is None:
            raise click.ClickException(
                "Unexpected response format from Anthropic API."
            )

        analysis_text = content_block.text
        if truncated:
            analysis_text += (
                "\n\n---\n"
                "*Note: This analysis was truncated "
                "due to length constraints.*"
            )

        return AnalysisResult(
            text=analysis_text,
            role=role.name,
            model=response.model,
            input_tokens=response.usage.input_tokens if not cache_hit else 0,
            output_tokens=response.usage.output_tokens if not cache_hit else 0,
            cache_hit=cache_hit,
            truncated=truncated,
        )
