"""Tests for the progress tracker (QUIL-21)."""

from io import StringIO
from unittest.mock import MagicMock, patch

from anthropic.types import Message, TextBlock, Usage
from rich.console import Console

from quill.analyzer import analyze_document_all_roles
from quill.progress import ProgressTracker, RoleStatus, _build_table
from quill.roles import ALL_ROLES


def _make_response(role_name: str) -> Message:
    return Message(
        id=f"msg_{role_name.replace(' ', '_').lower()}",
        type="message",
        role="assistant",
        content=[TextBlock(type="text", text=f"Analysis from {role_name}.")],
        model="claude-sonnet-4-20250514",
        stop_reason="end_turn",
        usage=Usage(input_tokens=100, output_tokens=50),
    )


class TestRoleStatus:
    def test_pending_is_default(self) -> None:
        tracker = ProgressTracker(ALL_ROLES)
        for role in ALL_ROLES:
            assert tracker.statuses[role.name] == RoleStatus.PENDING

    def test_update_changes_status(self) -> None:
        tracker = ProgressTracker(ALL_ROLES)
        tracker.update("Law Clerk", RoleStatus.IN_PROGRESS)
        assert tracker.statuses["Law Clerk"] == RoleStatus.IN_PROGRESS

    def test_update_to_completed(self) -> None:
        tracker = ProgressTracker(ALL_ROLES)
        tracker.update("Law Clerk", RoleStatus.IN_PROGRESS)
        tracker.update("Law Clerk", RoleStatus.COMPLETED)
        assert tracker.statuses["Law Clerk"] == RoleStatus.COMPLETED

    def test_update_to_failed(self) -> None:
        tracker = ProgressTracker(ALL_ROLES)
        tracker.update("Law Clerk", RoleStatus.FAILED)
        assert tracker.statuses["Law Clerk"] == RoleStatus.FAILED


class TestProgressTable:
    def test_table_shows_all_roles(self) -> None:
        statuses = {role.name: RoleStatus.PENDING for role in ALL_ROLES}
        table = _build_table(ALL_ROLES, statuses)
        assert table.row_count == 5

    def test_table_title(self) -> None:
        statuses = {role.name: RoleStatus.PENDING for role in ALL_ROLES}
        table = _build_table(ALL_ROLES, statuses)
        assert "Analyzing" in str(table.title)

    def test_table_renders_without_error(self) -> None:
        buf = StringIO()
        console = Console(file=buf, force_terminal=False, width=80)
        statuses = {role.name: RoleStatus.PENDING for role in ALL_ROLES}
        table = _build_table(ALL_ROLES, statuses)
        console.print(table)
        output = buf.getvalue()
        assert "Law Clerk" in output
        assert "Senior Partner" in output


class TestProgressTracker:
    def test_context_manager(self) -> None:
        console = Console(file=StringIO(), force_terminal=False)
        with ProgressTracker(ALL_ROLES, console=console) as tracker:
            tracker.update("Law Clerk", RoleStatus.COMPLETED)
        assert tracker.statuses["Law Clerk"] == RoleStatus.COMPLETED

    def test_make_callback_is_callable(self) -> None:
        tracker = ProgressTracker(ALL_ROLES)
        callback = tracker.make_callback()
        assert callable(callback)

    def test_callback_updates_status(self) -> None:
        tracker = ProgressTracker(ALL_ROLES)
        callback = tracker.make_callback()
        callback("Senior Partner", RoleStatus.IN_PROGRESS)
        assert tracker.statuses["Senior Partner"] == RoleStatus.IN_PROGRESS

    def test_no_live_display_in_non_tty(self) -> None:
        console = Console(file=StringIO(), force_terminal=False)
        tracker = ProgressTracker(ALL_ROLES, console=console)
        tracker.start()
        assert tracker._live is None
        tracker.stop()

    def test_transient_output_when_piped(self) -> None:
        """Progress display should leave no artifacts when piped to a file."""
        buf = StringIO()
        console = Console(file=buf, force_terminal=False, no_color=True)
        with ProgressTracker(ALL_ROLES, console=console):
            pass
        output = buf.getvalue()
        assert "Analyzing" not in output


class TestProgressIntegration:
    def test_callback_fires_during_parallel_execution(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        status_log: list[tuple[str, RoleStatus]] = []

        def track(name: str, status: RoleStatus) -> None:
            status_log.append((name, status))

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = [
                _make_response(r.name) for r in ALL_ROLES
            ]
            analyze_document_all_roles("contract text", on_progress=track)

        role_names_started = {
            name for name, s in status_log if s == RoleStatus.IN_PROGRESS
        }
        role_names_completed = {
            name for name, s in status_log if s == RoleStatus.COMPLETED
        }
        expected_names = {r.name for r in ALL_ROLES}

        assert role_names_started == expected_names
        assert role_names_completed == expected_names

    def test_failed_role_fires_failed_status(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        status_log: list[tuple[str, RoleStatus]] = []

        def track(name: str, status: RoleStatus) -> None:
            status_log.append((name, status))

        import anthropic

        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            idx = call_count
            call_count += 1
            if idx == 0:
                raise anthropic.APIConnectionError(request=MagicMock())
            return _make_response(f"role_{idx}")

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = side_effect
            analyze_document_all_roles("contract text", on_progress=track)

        failed = [(n, s) for n, s in status_log if s == RoleStatus.FAILED]
        assert len(failed) >= 1

    def test_each_role_transitions_through_in_progress(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        status_log: list[tuple[str, RoleStatus]] = []

        def track(name: str, status: RoleStatus) -> None:
            status_log.append((name, status))

        with patch("quill.analyzer.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = [
                _make_response(r.name) for r in ALL_ROLES
            ]
            analyze_document_all_roles("contract text", on_progress=track)

        for role in ALL_ROLES:
            role_events = [s for n, s in status_log if n == role.name]
            assert RoleStatus.IN_PROGRESS in role_events
            assert role_events[-1] in (RoleStatus.COMPLETED, RoleStatus.FAILED)
