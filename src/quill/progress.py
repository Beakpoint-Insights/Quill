"""Live progress display for multi-role analysis."""

from collections.abc import Callable
from enum import Enum

from rich.console import Console
from rich.live import Live
from rich.table import Table

from quill.roles import Role

__all__ = ["RoleStatus", "ProgressTracker"]


class RoleStatus(Enum):
    """Status of a role during parallel execution."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


_STATUS_DISPLAY: dict[RoleStatus, tuple[str, str]] = {
    RoleStatus.PENDING: ("...", "dim"),
    RoleStatus.IN_PROGRESS: (">>>", "yellow"),
    RoleStatus.COMPLETED: ("ok", "green"),
    RoleStatus.FAILED: ("ERR", "red"),
}


def _build_table(
    roles: tuple[Role, ...],
    statuses: dict[str, RoleStatus],
) -> Table:
    """Build the progress table for display.

    Args:
        roles: The roles being executed.
        statuses: Current status of each role, keyed by name.

    Returns:
        A Rich Table showing role progress.
    """
    table = Table(
        title="Analyzing document...",
        show_header=True,
        expand=False,
    )
    table.add_column("Status", width=6, justify="center")
    table.add_column("Role", style="bold")
    table.add_column("Model")

    for role in roles:
        status = statuses.get(role.name, RoleStatus.PENDING)
        indicator, style = _STATUS_DISPLAY[status]
        table.add_row(
            f"[{style}]{indicator}[/{style}]",
            role.name,
            role.model,
        )

    return table


class ProgressTracker:
    """Tracks and displays role execution progress.

    Attributes:
        roles: The roles being tracked.
        statuses: Current status of each role.
    """

    def __init__(self, roles: tuple[Role, ...], console: Console | None = None) -> None:
        self._roles = roles
        self._statuses: dict[str, RoleStatus] = {
            role.name: RoleStatus.PENDING for role in roles
        }
        self._console = console or Console()
        self._live: Live | None = None

    @property
    def statuses(self) -> dict[str, RoleStatus]:
        """Return a copy of the current statuses."""
        return dict(self._statuses)

    def update(self, role_name: str, status: RoleStatus) -> None:
        """Update a role's status and refresh the display.

        Args:
            role_name: Name of the role to update.
            status: The new status.
        """
        self._statuses[role_name] = status
        if self._live is not None:
            self._live.update(_build_table(self._roles, self._statuses))

    def make_callback(self) -> Callable[[str, RoleStatus], None]:
        """Return a callback for passing to the analyzer.

        Returns:
            A callable accepting (role_name, status).
        """
        return self.update

    def start(self) -> None:
        """Start the live progress display."""
        if self._console.is_terminal:
            self._live = Live(
                _build_table(self._roles, self._statuses),
                console=self._console,
                refresh_per_second=4,
                transient=True,
            )
            self._live.start()

    def stop(self) -> None:
        """Stop the live progress display."""
        if self._live is not None:
            self._live.stop()
            self._live = None

    def __enter__(self) -> "ProgressTracker":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()
