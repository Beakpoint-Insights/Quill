import os
from pathlib import Path
from unittest.mock import patch

import pytest
from anthropic.types import Message, TextBlock, Usage

from quill.cache import ResponseCache

FIXTURES_DIR = Path(__file__).parent / "fixtures"

os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
os.environ.pop("OTEL_EXPORTER_OTLP_HEADERS", None)


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def sample_nda(fixtures_dir):
    return fixtures_dir / "nda" / "papertrail-short.md"


@pytest.fixture
def anthropic_response():
    return Message(
        id="msg_test_0001",
        type="message",
        role="assistant",
        content=[
            TextBlock(
                type="text",
                text="This document is a mutual non-disclosure agreement.",
            )
        ],
        model="claude-sonnet-4-20250514",
        stop_reason="end_turn",
        usage=Usage(input_tokens=1200, output_tokens=85),
    )


@pytest.fixture(autouse=True)
def _no_cache(tmp_path: Path) -> ResponseCache:
    """Point the response cache at a throwaway directory for all tests."""
    empty_cache = ResponseCache(cache_dir=tmp_path / "cache")
    with patch("quill.analyzer.ResponseCache", return_value=empty_cache):
        yield empty_cache


@pytest.fixture
def mock_anthropic(anthropic_response):
    with patch("anthropic.Anthropic") as mock_cls:
        client = mock_cls.return_value
        client.messages.create.return_value = anthropic_response
        yield client
