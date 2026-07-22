"""Document analysis using the Anthropic API."""

import asyncio
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass

import anthropic
import click
from anthropic.types import MessageParam, TextBlock
from opentelemetry import trace

from quill.cache import ResponseCache
from quill.progress import RoleStatus
from quill.roles import ALL_ROLES, SENIOR_PARTNER, Role

__all__ = ["AnalysisResult", "analyze_document", "analyze_document_all_roles"]

ProgressCallback = Callable[[str, RoleStatus], None]

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


def _require_api_key(api_key: str | None = None) -> str:
    """Resolve the API key from the argument or environment.

    Args:
        api_key: Explicit key, or None to read from env.

    Returns:
        The resolved API key.

    Raises:
        click.ClickException: If no key is available.
    """
    resolved = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not resolved:
        raise click.ClickException(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Get your key at https://console.anthropic.com/"
        )
    return resolved


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
    resolved_key = _require_api_key(api_key)
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
            raise click.ClickException("Unexpected response format from Anthropic API.")

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


async def _analyze_role(
    text: str,
    role: Role,
    api_key: str,
    on_progress: ProgressCallback | None = None,
) -> AnalysisResult:
    """Run a single role's analysis in a thread, returning an error result on failure.

    Args:
        text: The document text to analyze.
        role: The role to execute.
        api_key: Anthropic API key.
        on_progress: Optional callback for status updates.

    Returns:
        An AnalysisResult — either a success or an error result.
    """
    if on_progress:
        on_progress(role.name, RoleStatus.IN_PROGRESS)

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: analyze_document(text, role, api_key=api_key),
        )
        if on_progress:
            on_progress(role.name, RoleStatus.COMPLETED)
        return result
    except (click.ClickException, Exception) as exc:
        error_msg = exc.message if isinstance(exc, click.ClickException) else str(exc)
        logger.error("Role %s failed: %s", role.name, error_msg)
        if on_progress:
            on_progress(role.name, RoleStatus.FAILED)
        return AnalysisResult(
            text="",
            role=role.name,
            model=role.model,
            input_tokens=0,
            output_tokens=0,
            error=error_msg,
        )


async def _analyze_all_roles_async(
    text: str,
    roles: tuple[Role, ...],
    api_key: str,
    on_progress: ProgressCallback | None = None,
) -> list[AnalysisResult]:
    """Fan out all roles concurrently and collect results.

    Args:
        text: The document text to analyze.
        roles: The roles to execute.
        api_key: Anthropic API key.
        on_progress: Optional callback for status updates.

    Returns:
        A list of AnalysisResults in the same order as the input roles.
    """
    tasks = [_analyze_role(text, role, api_key, on_progress) for role in roles]
    return list(await asyncio.gather(*tasks))


def analyze_document_all_roles(
    text: str,
    roles: tuple[Role, ...] = ALL_ROLES,
    *,
    api_key: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> list[AnalysisResult]:
    """Analyze a legal document with all roles in parallel.

    Args:
        text: The document text to analyze.
        roles: Roles to execute (defaults to ALL_ROLES).
        api_key: Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.
        on_progress: Optional callback for status updates.

    Returns:
        A list of AnalysisResults, one per role, in role order.

    Raises:
        click.ClickException: On missing API key.
    """
    resolved_key = _require_api_key(api_key)

    with tracer.start_as_current_span(
        "quill.analyze_all",
        attributes={
            "code.function.name": "quill.analyzer.analyze_document_all_roles",
            "quill.roles.count": len(roles),
        },
    ):
        return asyncio.run(
            _analyze_all_roles_async(text, roles, resolved_key, on_progress)
        )
