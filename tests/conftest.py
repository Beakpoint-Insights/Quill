from pathlib import Path
from unittest.mock import patch

import pytest
from anthropic.types import Message, TextBlock, Usage


FIXTURES_DIR = Path(__file__).parent / "fixtures"


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
        content=[TextBlock(type="text", text="This document is a mutual non-disclosure agreement.")],
        model="claude-sonnet-4-20250514",
        stop_reason="end_turn",
        usage=Usage(input_tokens=1200, output_tokens=85),
    )


@pytest.fixture
def mock_anthropic(anthropic_response):
    with patch("anthropic.Anthropic") as mock_cls:
        client = mock_cls.return_value
        client.messages.create.return_value = anthropic_response
        yield client
