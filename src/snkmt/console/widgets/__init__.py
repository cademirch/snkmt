from textual import events
from textual.message import Message
from textual.widgets import DataTable, Footer, Header, Input, Static
from textual.screen import Screen
from textual.app import App, ComposeResult


class Table(DataTable):
    """
    Generic DataTable that uses Enter key to select cells.
    """

    class Selected(Message):
        def __init__(self, table: "Table"):
            super().__init__()
            self.table = table

    def key_enter(self, event: events.Key) -> bool:
        """
        Callback for pressing enter key.
        """
        return self.post_message(self.Selected(self))
