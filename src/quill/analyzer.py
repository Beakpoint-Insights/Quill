import os
from dataclasses import dataclass

import anthropic
import click


@dataclass
class AnalysisResult:
    text: str
    role: str
    model: str
    input_tokens: int
    output_tokens: int


SENIOR_PARTNER_PROMPT = """\
You are a Senior Partner at a top-tier law firm with 30 years of experience. \
Analyze the following legal document and provide your assessment in this structure:

## Executive Summary
A concise overview of what this document is, its purpose, and the parties involved.

## Strategic Assessment
Your professional evaluation of the document's strengths, weaknesses, and overall quality.

## Key Risks
Specific risks, liabilities, or concerns that a client should be aware of before signing.

## Negotiation Recommendations
Concrete suggestions for terms to negotiate, modify, or add before execution.\
"""


def analyze_document(text: str) -> AnalysisResult:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise click.ClickException(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Get your key at https://console.anthropic.com/"
        )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-opus-4",
            max_tokens=4096,
            system=SENIOR_PARTNER_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
    except anthropic.AuthenticationError:
        raise click.ClickException("Invalid ANTHROPIC_API_KEY. Check your API key and try again.")
    except anthropic.RateLimitError:
        raise click.ClickException("Rate limited by the Anthropic API. Please wait and try again.")
    except anthropic.APIConnectionError:
        raise click.ClickException("Could not connect to the Anthropic API. Check your network connection.")
    except anthropic.APIError as e:
        raise click.ClickException(f"Anthropic API error: {e}")

    return AnalysisResult(
        text=response.content[0].text,
        role="Senior Partner",
        model=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
