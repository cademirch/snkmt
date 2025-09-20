from textual.command import Hit, Hits, Provider, DiscoveryHit, CommandPalette
from textual.screen import ModalScreen
from textual.widgets import Input, Label
from textual.containers import Vertical
from textual.app import ComposeResult
from functools import partial
from typing import cast, Callable, TYPE_CHECKING
from snkmt.core.config import DatabaseConfig

if TYPE_CHECKING:
    from snkmt.console.app import snkmtApp


class CustomSourceModal(ModalScreen):
    """Modal for entering a custom database source."""

    CSS = """
    CustomSourceModal {
        align: center middle;
    }
    
    CustomSourceModal > Vertical {
        width: 60;
        height: 11;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }
    
    CustomSourceModal Input {
        margin: 1 0;
    }
    """

    BINDINGS = [
        ("escape", "dismiss", "Cancel"),
    ]

    @property
    def app(self) -> "snkmtApp":
        return cast("snkmtApp", super().app)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Enter database source URL:")
            yield Input(
                placeholder="/path/to/db",
                id="source-input",
            )
            yield Label("[dim]Press Enter to connect, Escape to cancel[/dim]")

    def on_mount(self) -> None:
        """Focus the input when modal opens."""
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission when Enter is pressed."""
        if source := event.value.strip():
            self.app.set_database_source(source)
            self.dismiss()


class DatabaseSourceProvider(Provider):
    """Provider for database source selection."""

    @property
    def app(self) -> "snkmtApp":
        return cast("snkmtApp", super().app)

    @property
    def sources(self) -> list[str]:
        dbs = DatabaseConfig().list_databases()
        config_dbs = set(str(db.path) for db in dbs)
        if self.app.databases:
            for db in self.app.databases:
                config_dbs.add(db)
        return list(config_dbs)

    @property
    def commands(self) -> list[tuple[str, Callable[[], None]]]:
        """Generate list of (display, callback) tuples for sources."""

        def set_database_source(url: str) -> None:
            self.app.set_database_source(url)

        def open_custom_input() -> None:
            self.app.push_screen(CustomSourceModal())

        commands = [
            (source, partial(set_database_source, source)) for source in self.sources
        ]

        # Add custom entry option at the end
        commands.append(("Enter source...", open_custom_input))  # type: ignore

        return commands

    async def discover(self) -> Hits:
        """Show all available database sources."""
        for display, callback in self.commands:
            yield DiscoveryHit(display, callback)

    async def search(self, query: str) -> Hits:
        """Search through database sources."""
        matcher = self.matcher(query)

        for display, callback in self.commands:
            if (score := matcher.match(display)) > 0:
                yield Hit(
                    score,
                    matcher.highlight(display),
                    callback,
                )


class SelectDatabaseCommand(Provider):
    """Single command to open database source selector."""

    async def discover(self) -> Hits:
        yield DiscoveryHit(
            display="Select database source",
            command=self.open_source_selector,
            help="Choose a database source to connect to",
        )

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        score = matcher.match("select database source")
        if score > 0:
            yield Hit(
                score,
                matcher.highlight("Select database source"),
                self.open_source_selector,
                help="Choose a database source to connect to",
            )

    def open_source_selector(self) -> None:
        self.app.push_screen(
            CommandPalette(
                providers=[DatabaseSourceProvider],
                placeholder="Search for database sources…",
            )
        )
