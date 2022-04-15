"""This module provides the logme model-controller."""

from pathlib import Path
from typing import Any, Dict, List, NamedTuple

from logme import DB_READ_ERROR, ID_ERROR, creds_dict
from logme.database import DatabaseHandler

class CurrentLogme(NamedTuple):
    todo: Dict[str, Any]
    error: int


class DownloadDrive:
    """Class to download log files from Google Drive."""
    # @todo

class Todoer:
    def __init__(self, db_path: Path) -> None:
        self._db_handler = DatabaseHandler(db_path)

    def add(self, description: List[str], priority: int = 2) -> CurrentLogme:
        """Add a new to-do to the database."""
        description_text = " ".join(description)
        if not description_text.endswith("."):
            description_text += "."
        todo = {
            "Description": description_text,
            "Priority": priority,
            "Done": False,
        }
        read = self._db_handler.read_logme()
        if read.error == DB_READ_ERROR:
            return CurrentLogme(todo, read.error)
        read.todo_list.append(todo)
        write = self._db_handler.write_logme(read.todo_list)
        return CurrentLogme(todo, write.error)

    def get_todo_list(self) -> List[Dict[str, Any]]:
        """Return the current to-do list."""
        read = self._db_handler.read_logme()
        return read.todo_list

    def set_done(self, todo_id: int) -> CurrentLogme:
        """Set a to-do as done."""
        read = self._db_handler.read_logme()
        if read.error:
            return CurrentLogme({}, read.error)
        try:
            todo = read.todo_list[todo_id - 1]
        except IndexError:
            return CurrentLogme({}, ID_ERROR)
        todo["Done"] = True
        write = self._db_handler.write_logme(read.todo_list)
        return CurrentLogme(todo, write.error)

    def remove(self, todo_id: int) -> CurrentLogme:
        """Remove a to-do from the database using its id or index."""
        read = self._db_handler.read_logme()
        if read.error:
            return CurrentLogme({}, read.error)
        try:
            todo = read.todo_list.pop(todo_id - 1)
        except IndexError:
            return CurrentLogme({}, ID_ERROR)
        write = self._db_handler.write_logme(read.todo_list)
        return CurrentLogme(todo, write.error)

    def remove_all(self) -> CurrentLogme:
        """Remove all to-dos from the database."""
        write = self._db_handler.write_logme([])
        return CurrentLogme({}, write.error)
