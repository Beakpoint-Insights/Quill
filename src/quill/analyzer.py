"""Document analysis using multiple LLM providers."""

import asyncio
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass

import anthropic
import click
import openai
from anthropic.types import MessageParam, TextBlock
from opentelemetry import context as otel_context
from opentelemetry import trace

from quill.cache import ResponseCache
from quill.progress import RoleStatus
from quill.prompts import get_system_prompt
from quill.roles import ALL_ROLES, SENIOR_PARTNER, Role
from quill.tracing import get_department

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
        provider: The LLM provider (``"anthropic"`` or ``"openai"``).
        model: The model identifier.
        input_tokens: Input tokens consumed (zero on cache hit).
        output_tokens: Output tokens consumed (zero on cache hit).
        cache_hit: Whether the result was served from cache.
        truncated: Whether the API response was truncated.
        error: Error message if the analysis failed, None on success.
    """

    text: str
    role: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_hit: bool = False
    truncated: bool = False
    error: str | None = None


def _require_anthropic_key(api_key: str | None = None) -> str:
    """Resolve the Anthropic API key from the argument or environment.

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


def _require_openai_key() -> str:
    """Resolve the OpenAI API key from the environment.

    Returns:
        The resolved API key.

    Raises:
        click.ClickException: If no key is available.
    """
    resolved = os.environ.get("OPENAI_API_KEY")
    if not resolved:
        raise click.ClickException(
            "OPENAI_API_KEY environment variable is not set. "
            "Get your key at https://platform.openai.com/api-keys"
        )
    return resolved


def _preflight_check_keys(roles: tuple[Role, ...], api_key: str | None) -> None:
    """Fail fast if any required API key is missing.

    Args:
        roles: The roles that will be executed.
        api_key: Explicit Anthropic API key, or None to read from env.

    Raises:
        click.ClickException: If a required key is absent.
    """
    providers = {r.provider for r in roles}
    missing: list[str] = []
    if "anthropic" in providers:
        resolved = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not resolved:
            missing.append(
                "ANTHROPIC_API_KEY is not set (https://console.anthropic.com/)"
            )
    if "openai" in providers and not os.environ.get("OPENAI_API_KEY"):
        missing.append(
            "OPENAI_API_KEY is not set (https://platform.openai.com/api-keys)"
        )
    if missing:
        raise click.ClickException(
            "Missing API keys — no calls were made.\n  " + "\n  ".join(missing)
        )


def _call_anthropic(
    text: str,
    role: Role,
    api_key: str | None,
    system_prompt: str | None = None,
) -> AnalysisResult:
    """Execute a single analysis call via the Anthropic API.

    Args:
        text: The document text to analyze.
        role: The role definition.
        api_key: Explicit Anthropic API key, or None to read from env.
        system_prompt: Override for the role's default system prompt.

    Returns:
        An AnalysisResult with the model's response.

    Raises:
        click.ClickException: On API errors or missing key.
    """
    resolved_key = _require_anthropic_key(api_key)
    prompt = system_prompt if system_prompt is not None else role.system_prompt
    try:
        client = anthropic.Anthropic(api_key=resolved_key)
        messages: list[MessageParam] = [{"role": "user", "content": text}]
        response = client.messages.create(
            model=role.model,
            max_tokens=4096,
            system=prompt,
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
            "Could not connect to the Anthropic API. Check your network connection."
        ) from None
    except anthropic.APIError as e:
        raise click.ClickException(f"Anthropic API error: {e}") from None

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
            "\n\n---\n*Note: This analysis was truncated due to length constraints.*"
        )

    return AnalysisResult(
        text=analysis_text,
        role=role.name,
        provider="anthropic",
        model=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        truncated=truncated,
    )


def _call_openai(
    text: str,
    role: Role,
    system_prompt: str | None = None,
) -> AnalysisResult:
    """Execute a single analysis call via the OpenAI API.

    Args:
        text: The document text to analyze.
        role: The role definition.
        system_prompt: Override for the role's default system prompt.

    Returns:
        An AnalysisResult with the model's response.

    Raises:
        click.ClickException: On API errors or missing key.
    """
    resolved_key = _require_openai_key()
    prompt = system_prompt if system_prompt is not None else role.system_prompt
    try:
        client = openai.OpenAI(api_key=resolved_key)
        response = client.chat.completions.create(
            model=role.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
        )
    except openai.AuthenticationError:
        raise click.ClickException(
            "Invalid OPENAI_API_KEY. Check your API key and try again."
        ) from None
    except openai.RateLimitError:
        raise click.ClickException(
            "Rate limited by the OpenAI API. Please wait and try again."
        ) from None
    except openai.APIConnectionError:
        raise click.ClickException(
            "Could not connect to the OpenAI API. Check your network connection."
        ) from None
    except openai.APIError as e:
        raise click.ClickException(f"OpenAI API error: {e}") from None

    choice = response.choices[0] if response.choices else None
    if choice is None or choice.message.content is None:
        raise click.ClickException("Unexpected response format from OpenAI API.")

    truncated = choice.finish_reason == "length"
    if truncated:
        logger.warning("Response was truncated (max_tokens reached)")

    analysis_text = choice.message.content
    if truncated:
        analysis_text += (
            "\n\n---\n*Note: This analysis was truncated due to length constraints.*"
        )

    input_tokens = response.usage.prompt_tokens if response.usage else 0
    output_tokens = response.usage.completion_tokens if response.usage else 0

    return AnalysisResult(
        text=analysis_text,
        role=role.name,
        provider="openai",
        model=response.model or role.model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        truncated=truncated,
    )


def analyze_document(
    text: str,
    role: Role = SENIOR_PARTNER,
    *,
    api_key: str | None = None,
    no_cache: bool = False,
    doc_type: str | None = None,
) -> AnalysisResult:
    """Analyze a legal document using the appropriate LLM provider.

    Args:
        text: The document text to analyze.
        role: The role to use for analysis.
        api_key: Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.
            Ignored for OpenAI roles (uses OPENAI_API_KEY env var).
        no_cache: When True, bypass the local response cache.
        doc_type: Document type for prompt specialisation (e.g. ``"nda"``,
            ``"msa"``, ``"employment"``).  ``None`` uses the generic prompt.

    Returns:
        An AnalysisResult with the model's assessment.

    Raises:
        click.ClickException: On missing API key or API errors.
    """
    cache = ResponseCache()
    system_prompt = get_system_prompt(role, doc_type)

    span_attrs: dict[str, str | bool | int] = {
        "code.function.name": "quill.analyzer.analyze_document",
        "quill.role": role.name,
        "quill.model": role.model,
        "quill.provider": role.provider,
    }
    if doc_type is not None:
        span_attrs["quill.doc_type"] = doc_type
    dept = get_department()
    if dept is not None:
        span_attrs["app.user.org.id"] = dept

    with tracer.start_as_current_span(
        "quill.analyze",
        attributes=span_attrs,
    ) as span:
        cached_result = None if no_cache else cache.get(role.model, system_prompt, text)
        cache_hit = cached_result is not None
        span.set_attribute("quill.cache.hit", cache_hit)

        if cached_result is not None:
            span.set_attribute("gen_ai.usage.input_tokens", 0)
            span.set_attribute("gen_ai.usage.output_tokens", 0)
            return cached_result

        if role.provider == "openai":
            result = _call_openai(text, role, system_prompt)
        else:
            result = _call_anthropic(text, role, api_key, system_prompt)

        span.set_attribute("gen_ai.usage.input_tokens", result.input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", result.output_tokens)

        try:
            cache.put(role.model, system_prompt, text, result)
        except OSError:
            logger.warning("Failed to write cache, continuing with result")

        return result


async def _analyze_role(
    text: str,
    role: Role,
    api_key: str | None,
    on_progress: ProgressCallback | None = None,
    no_cache: bool = False,
    doc_type: str | None = None,
) -> AnalysisResult:
    """Run a single role's analysis in a thread, returning an error result on failure.

    Args:
        text: The document text to analyze.
        role: The role to execute.
        api_key: Anthropic API key, or None to read from env.
        on_progress: Optional callback for status updates.
        no_cache: When True, bypass the local response cache.
        doc_type: Document type for prompt specialisation.

    Returns:
        An AnalysisResult -- either a success or an error result.
    """
    loop = asyncio.get_running_loop()
    ctx = otel_context.get_current()
    try:
        if on_progress:
            on_progress(role.name, RoleStatus.IN_PROGRESS)

        def _run_with_context() -> AnalysisResult:
            token = otel_context.attach(ctx)
            try:
                return analyze_document(
                    text, role, api_key=api_key, no_cache=no_cache, doc_type=doc_type
                )
            finally:
                otel_context.detach(token)

        result = await loop.run_in_executor(None, _run_with_context)
        if on_progress:
            on_progress(role.name, RoleStatus.COMPLETED)
        return result
    except Exception as exc:
        error_msg = exc.message if isinstance(exc, click.ClickException) else str(exc)
        logger.error("Role %s failed: %s", role.name, error_msg)
        if on_progress:
            on_progress(role.name, RoleStatus.FAILED)
        return AnalysisResult(
            text="",
            role=role.name,
            provider=role.provider,
            model=role.model,
            input_tokens=0,
            output_tokens=0,
            error=error_msg,
        )


async def _analyze_all_roles_async(
    text: str,
    roles: tuple[Role, ...],
    api_key: str | None,
    on_progress: ProgressCallback | None = None,
    no_cache: bool = False,
    doc_type: str | None = None,
) -> list[AnalysisResult]:
    """Fan out all roles concurrently and collect results.

    Args:
        text: The document text to analyze.
        roles: The roles to execute.
        api_key: Anthropic API key, or None to read from env.
        on_progress: Optional callback for status updates.
        no_cache: When True, bypass the local response cache.
        doc_type: Document type for prompt specialisation.

    Returns:
        A list of AnalysisResults in the same order as the input roles.
    """
    tasks = [
        _analyze_role(
            text, role, api_key, on_progress, no_cache=no_cache, doc_type=doc_type
        )
        for role in roles
    ]
    return list(await asyncio.gather(*tasks))


def analyze_document_all_roles(
    text: str,
    roles: tuple[Role, ...] = ALL_ROLES,
    *,
    api_key: str | None = None,
    on_progress: ProgressCallback | None = None,
    no_cache: bool = False,
    doc_type: str | None = None,
) -> list[AnalysisResult]:
    """Analyze a legal document with all roles in parallel.

    Args:
        text: The document text to analyze.
        roles: Roles to execute (defaults to ALL_ROLES).
        api_key: Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.
        on_progress: Optional callback for status updates.
        no_cache: When True, bypass the local response cache.
        doc_type: Document type for prompt specialisation (e.g. ``"nda"``).

    Returns:
        A list of AnalysisResults, one per role, in role order.
        Individual results carry an error if the API key is missing.
    """
    all_span_attrs: dict[str, str | int] = {
        "code.function.name": "quill.analyzer.analyze_document_all_roles",
        "quill.roles.count": len(roles),
    }
    if doc_type is not None:
        all_span_attrs["quill.doc_type"] = doc_type
    dept = get_department()
    if dept is not None:
        all_span_attrs["app.user.org.id"] = dept

    _preflight_check_keys(roles, api_key)

    with tracer.start_as_current_span(
        "quill.analyze_all",
        attributes=all_span_attrs,
    ):
        return asyncio.run(
            _analyze_all_roles_async(
                text, roles, api_key, on_progress, no_cache=no_cache, doc_type=doc_type
            )
        )
