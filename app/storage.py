from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from .business import defaults, validate_state


class StorageError(RuntimeError):
    pass


class BudgetStorage:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute(
                        "CREATE TABLE IF NOT EXISTS app_state ("
                        "id INTEGER PRIMARY KEY CHECK(id = 1), payload TEXT NOT NULL, updated_at TEXT NOT NULL)"
                    )
                    row = connection.execute(
                        "SELECT payload FROM app_state WHERE id = 1"
                    ).fetchone()
            if row is None:
                self.save(defaults())
            else:
                self.load()
        except (sqlite3.Error, OSError, ValueError) as error:
            raise StorageError(f"Could not open the data store at {self.path}: {error}") from error

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def load(self) -> dict[str, Any]:
        try:
            with closing(self._connect()) as connection:
                with connection:
                    row = connection.execute(
                        "SELECT payload FROM app_state WHERE id = 1"
                    ).fetchone()
            if row is None:
                raise StorageError("The application data record is missing.")
            return validate_state(json.loads(row[0]))
        except (sqlite3.Error, OSError, json.JSONDecodeError, ValueError) as error:
            if isinstance(error, StorageError):
                raise
            raise StorageError(
                f"Stored data is invalid or unreadable. It has not been replaced: {error}"
            ) from error

    def save(self, state: dict[str, Any]) -> None:
        validated = validate_state(state)
        payload = json.dumps(validated, ensure_ascii=False, allow_nan=False)
        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute(
                        "INSERT INTO app_state(id, payload, updated_at) VALUES(1, ?, datetime('now')) "
                        "ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                        (payload,),
                    )
        except (sqlite3.Error, OSError) as error:
            raise StorageError(f"Could not save your data: {error}") from error

    @staticmethod
    def read_json(path: str | Path) -> dict[str, Any]:
        try:
            with Path(path).open("r", encoding="utf-8") as file:
                return validate_state(json.load(file))
        except (OSError, json.JSONDecodeError, ValueError) as error:
            raise StorageError(f"Could not import this data file: {error}") from error

    @staticmethod
    def write_json(path: str | Path, state: dict[str, Any]) -> None:
        validated = validate_state(state)
        target = Path(path)
        temporary = target.with_name(target.name + ".tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as file:
                json.dump(validated, file, ensure_ascii=False, indent=2, allow_nan=False)
                file.write("\n")
            temporary.replace(target)
        except OSError as error:
            raise StorageError(f"Could not export your data: {error}") from error
