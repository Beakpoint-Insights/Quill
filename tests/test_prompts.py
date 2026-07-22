"""Tests for document-type-specific prompt variants (QUIL-8)."""

import logging

from quill.prompts import DOCUMENT_TYPES, VARIANT_REGISTRY, get_system_prompt
from quill.roles import ALL_ROLES


class TestDocumentTypes:
    def test_supported_types(self) -> None:
        assert {"nda", "msa", "employment"} == DOCUMENT_TYPES

    def test_every_role_has_variant_for_each_type(self) -> None:
        for role in ALL_ROLES:
            for doc_type in DOCUMENT_TYPES:
                key = (role.name, doc_type)
                assert key in VARIANT_REGISTRY, (
                    f"Missing variant for ({role.name!r}, {doc_type!r})"
                )

    def test_variant_prompts_are_non_empty_strings(self) -> None:
        for key, prompt in VARIANT_REGISTRY.items():
            assert isinstance(prompt, str)
            assert len(prompt) > 50, f"Variant {key} is suspiciously short"

    def test_variant_prompts_differ_from_generic(self) -> None:
        for role in ALL_ROLES:
            for doc_type in DOCUMENT_TYPES:
                variant = VARIANT_REGISTRY[(role.name, doc_type)]
                assert variant != role.system_prompt, (
                    f"Variant for ({role.name!r}, {doc_type!r}) "
                    f"is identical to the generic prompt"
                )


class TestGetSystemPrompt:
    def test_returns_generic_when_no_doc_type(self) -> None:
        for role in ALL_ROLES:
            result = get_system_prompt(role)
            assert result == role.system_prompt

    def test_returns_generic_when_doc_type_is_none(self) -> None:
        for role in ALL_ROLES:
            result = get_system_prompt(role, doc_type=None)
            assert result == role.system_prompt

    def test_returns_variant_for_known_type(self) -> None:
        for role in ALL_ROLES:
            for doc_type in DOCUMENT_TYPES:
                result = get_system_prompt(role, doc_type=doc_type)
                expected = VARIANT_REGISTRY[(role.name, doc_type)]
                assert result == expected

    def test_falls_back_to_generic_for_unknown_type(self) -> None:
        for role in ALL_ROLES:
            result = get_system_prompt(role, doc_type="lease")
            assert result == role.system_prompt

    def test_normalizes_case_and_whitespace(self) -> None:
        for role in ALL_ROLES:
            upper = get_system_prompt(role, doc_type="NDA")
            padded = get_system_prompt(role, doc_type="  nda  ")
            expected = VARIANT_REGISTRY[(role.name, "nda")]
            assert upper == expected
            assert padded == expected

    def test_logs_variant_selection(self, caplog: logging.LogRecord) -> None:
        role = ALL_ROLES[0]
        with caplog.at_level(logging.DEBUG, logger="quill.prompts"):
            get_system_prompt(role, doc_type="nda")
        assert "nda prompt variant" in caplog.text
        assert role.name in caplog.text

    def test_logs_fallback_for_unknown_type(self, caplog: logging.LogRecord) -> None:
        role = ALL_ROLES[0]
        with caplog.at_level(logging.DEBUG, logger="quill.prompts"):
            get_system_prompt(role, doc_type="lease")
        assert "falling back to generic" in caplog.text

    def test_logs_generic_when_no_type(self, caplog: logging.LogRecord) -> None:
        role = ALL_ROLES[0]
        with caplog.at_level(logging.DEBUG, logger="quill.prompts"):
            get_system_prompt(role)
        assert "generic prompt" in caplog.text


class TestNDAVariants:
    def test_nda_prompts_mention_confidential(self) -> None:
        for role in ALL_ROLES:
            prompt = get_system_prompt(role, doc_type="nda")
            lower = prompt.lower()
            assert "nda" in lower or "non-disclosure" in lower


class TestMSAVariants:
    def test_msa_prompts_mention_services(self) -> None:
        for role in ALL_ROLES:
            prompt = get_system_prompt(role, doc_type="msa")
            lower = prompt.lower()
            assert "msa" in lower or "master services" in lower


class TestEmploymentVariants:
    def test_employment_prompts_mention_employment(self) -> None:
        for role in ALL_ROLES:
            prompt = get_system_prompt(role, doc_type="employment")
            lower = prompt.lower()
            assert "employment" in lower
