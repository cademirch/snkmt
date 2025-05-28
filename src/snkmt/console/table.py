from typing import Any, Dict, List, Optional, Callable, Hashable
from textual.widgets import DataTable
from textual.widgets.data_table import ColumnKey
from textual import events
from textual.message import Message
from datetime import datetime
from rich.text import TextType


class UpdatingDataTable(DataTable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._column_keys: List[ColumnKey] = []
        self.cursor_type = "row"
        self.cursor_foreground_priority = "renderable"

    def add_columns(self, *labels: TextType) -> list:
        """Override add_columns to store the keys in order."""
        keys = super().add_columns(*labels)
        self._column_keys = keys
        return keys

    def update_row(self, key: str, row_data: List[TextType]) -> None:
        """Update a single row, adding it if it doesn't exist."""
        if key not in self.rows:
            self.add_row(*row_data, key=key)
        else:
            existing_row = self.get_row(key)
            if existing_row != row_data:
                for col_idx, (new_val, old_val) in enumerate(
                    zip(row_data, existing_row)
                ):
                    if new_val != old_val:
                        column_key = self._column_keys[col_idx]
                        self.update_cell(key, column_key, new_val)

    class Selected(Message):
        def __init__(self, table: "UpdatingDataTable"):
            super().__init__()
            self.table = table

    def key_enter(self, event: events.Key) -> bool:
        """
        Callback for pressing enter key.
        """
        return self.post_message(self.Selected(self))
