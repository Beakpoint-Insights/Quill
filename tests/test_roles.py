"""Tests for the roles module."""

import pytest

from quill.roles import (
    ALL_ROLES,
    JUNIOR_ASSOCIATE,
    LAW_CLERK,
    PARALEGAL,
    RESEARCH_ASSISTANT,
    SENIOR_PARTNER,
    Role,
    get_role,
)


class TestRoleDefinitions:
    def test_all_roles_contains_five_entries(self) -> None:
        assert len(ALL_ROLES) == 5

    def test_all_roles_order(self) -> None:
        names = [r.name for r in ALL_ROLES]
        assert names == [
            "Law Clerk",
            "Research Assistant",
            "Paralegal",
            "Junior Associate",
            "Senior Partner",
        ]

    def test_role_names_are_unique(self) -> None:
        names = [r.name for r in ALL_ROLES]
        assert len(names) == len(set(names))

    def test_all_roles_have_nonempty_prompts(self) -> None:
        for role in ALL_ROLES:
            assert role.system_prompt, f"{role.name} has empty system prompt"
            assert len(role.system_prompt) > 50, f"{role.name} prompt is too short"

    def test_role_is_frozen_dataclass(self) -> None:
        with pytest.raises(AttributeError):
            LAW_CLERK.name = "changed"  # type: ignore[misc]

    def test_all_roles_have_valid_provider(self) -> None:
        for role in ALL_ROLES:
            assert role.provider in ("anthropic", "openai"), (
                f"{role.name} has invalid provider: {role.provider}"
            )


class TestModelAssignments:
    def test_law_clerk_uses_anthropic_haiku(self) -> None:
        assert LAW_CLERK.provider == "anthropic"
        assert LAW_CLERK.model == "claude-haiku-4-5"

    def test_research_assistant_uses_openai_mini(self) -> None:
        assert RESEARCH_ASSISTANT.provider == "openai"
        assert RESEARCH_ASSISTANT.model == "gpt-4.1-mini"

    def test_paralegal_uses_openai(self) -> None:
        assert PARALEGAL.provider == "openai"
        assert PARALEGAL.model == "gpt-4.1"

    def test_junior_associate_uses_anthropic_sonnet(self) -> None:
        assert JUNIOR_ASSOCIATE.provider == "anthropic"
        assert JUNIOR_ASSOCIATE.model == "claude-sonnet-4-6"

    def test_senior_partner_uses_anthropic_top_tier(self) -> None:
        assert SENIOR_PARTNER.provider == "anthropic"
        assert SENIOR_PARTNER.model == "claude-sonnet-5"


class TestProviderDistribution:
    def test_three_anthropic_two_openai(self) -> None:
        anthropic_roles = [r for r in ALL_ROLES if r.provider == "anthropic"]
        openai_roles = [r for r in ALL_ROLES if r.provider == "openai"]
        assert len(anthropic_roles) == 3
        assert len(openai_roles) == 2

    def test_openai_roles_are_research_assistant_and_paralegal(self) -> None:
        openai_names = {r.name for r in ALL_ROLES if r.provider == "openai"}
        assert openai_names == {"Research Assistant", "Paralegal"}


class TestRolePromptContent:
    def test_law_clerk_prompt_covers_indexing(self) -> None:
        prompt = LAW_CLERK.system_prompt.lower()
        assert "document index" in prompt or "index" in prompt
        assert "section identification" in prompt or "section" in prompt
        assert "metadata" in prompt

    def test_research_assistant_prompt_covers_citations(self) -> None:
        prompt = RESEARCH_ASSISTANT.system_prompt.lower()
        assert "statut" in prompt
        assert "case" in prompt
        assert "regulat" in prompt or "citation" in prompt

    def test_paralegal_prompt_covers_clause_extraction(self) -> None:
        prompt = PARALEGAL.system_prompt.lower()
        assert "clause" in prompt
        assert "obligation" in prompt
        assert "deadline" in prompt
        assert "part" in prompt

    def test_junior_associate_prompt_covers_risk(self) -> None:
        prompt = JUNIOR_ASSOCIATE.system_prompt.lower()
        assert "risk" in prompt
        assert "unusual" in prompt
        assert "standard" in prompt

    def test_senior_partner_prompt_covers_strategy(self) -> None:
        prompt = SENIOR_PARTNER.system_prompt.lower()
        assert "executive summary" in prompt
        assert "strategic" in prompt or "assessment" in prompt
        assert "risk" in prompt
        assert "negotiat" in prompt


class TestGetRole:
    def test_get_role_exact_match(self) -> None:
        assert get_role("Senior Partner") is SENIOR_PARTNER

    def test_get_role_case_insensitive(self) -> None:
        assert get_role("law clerk") is LAW_CLERK
        assert get_role("LAW CLERK") is LAW_CLERK

    def test_get_role_unknown_raises(self) -> None:
        with pytest.raises(KeyError, match="Unknown role"):
            get_role("Intern")


class TestRoleDataclass:
    def test_role_equality(self) -> None:
        clone = Role(
            name=LAW_CLERK.name,
            provider=LAW_CLERK.provider,
            model=LAW_CLERK.model,
            system_prompt=LAW_CLERK.system_prompt,
        )
        assert clone == LAW_CLERK

    def test_role_is_iterable_for_fanout(self) -> None:
        roles_list = list(ALL_ROLES)
        assert len(roles_list) == 5
        assert all(isinstance(r, Role) for r in roles_list)
