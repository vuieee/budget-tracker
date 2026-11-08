from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.business import defaults
from app.storage import BudgetStorage, StorageError


class StorageTests(unittest.TestCase):
    def test_persistence_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.sqlite3"
            storage = BudgetStorage(path)
            state = defaults()
            state["categories"].append("Pets")
            storage.save(state)
            reopened = BudgetStorage(path)
            self.assertIn("Pets", reopened.load()["categories"])

    def test_invalid_stored_data_is_not_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.sqlite3"
            storage = BudgetStorage(path)
            damaged = '{"expenses": "not a list"}'
            with closing(sqlite3.connect(path)) as connection:
                with connection:
                    connection.execute("UPDATE app_state SET payload = ? WHERE id = 1", (damaged,))
            with self.assertRaises(StorageError):
                storage.load()
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute("SELECT payload FROM app_state").fetchone()[0], damaged)

    def test_json_export_import_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "export.json"
            state = defaults()
            state["settings"]["currency"] = "€"
            BudgetStorage.write_json(path, state)
            self.assertEqual(BudgetStorage.read_json(path)["settings"]["currency"], "€")

    def test_corrupt_json_import_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text('{"bad": ', encoding="utf-8")
            with self.assertRaises(StorageError):
                BudgetStorage.read_json(path)


if __name__ == "__main__":
    unittest.main()
