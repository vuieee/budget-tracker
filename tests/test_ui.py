from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QDoubleSpinBox, QLineEdit,
    QMessageBox, QTextEdit,
)

from app.storage import BudgetStorage
from app.ui import BudgetWindow, EntryDialog


class DesktopSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_window_renders_all_tabs_and_persists_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = BudgetStorage(Path(directory) / "budget.sqlite3")
            window = BudgetWindow(storage)
            window.show()
            self.application.processEvents()
            self.assertEqual(window.tabs.count(), 6)
            self.assertEqual(window.tabs.tabText(0), "Dashboard")
            self.assertEqual(window.tabs.tabText(5), "Settings")
            window.tabs.setCurrentIndex(4)
            self.application.processEvents()
            candidate = dict(window.state)
            candidate["settings"] = {**window.state["settings"], "currency": "$"}
            self.assertTrue(window._save_state(candidate))
            self.assertEqual(storage.load()["settings"]["currency"], "$")
            window.close()

    def test_create_edit_payment_delete_and_undo_workflows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = BudgetStorage(Path(directory) / "budget.sqlite3")
            window = BudgetWindow(storage)

            def accept_form(dialog: EntryDialog) -> int:
                today = QDate.currentDate()
                values = {
                    "Add Expense": {
                        "title": "Lunch", "amount": 75, "date": today, "category": "Food",
                        "method": "Bank", "notes": "team meal",
                    },
                    "Edit Expense": {
                        "title": "Dinner", "amount": 80, "date": today, "category": "Food",
                        "method": "Cash", "notes": "edited",
                    },
                    "New Savings Goal": {
                        "name": "Emergency", "target": 5000, "startDate": today,
                        "targetDate": today.addDays(60), "method": "weekly", "customDays": 7,
                    },
                    "Quick Contribution": {"goal": "Emergency", "amount": 250},
                    "New Debt Entry": {
                        "direction": "owed-to-me", "borrower": "Lee", "amount": 300,
                        "dateBorrowed": today, "rate": 0, "dueDate": today.addDays(30),
                        "interestType": "none", "interestFreq": "monthly", "phone": "",
                        "status": "active", "notes": "",
                    },
                    "Record Payment": {"amount": 100, "date": today, "notes": "partial"},
                }[dialog.windowTitle()]
                for key, value in values.items():
                    field = dialog.fields[key]
                    if isinstance(field, QLineEdit):
                        field.setText(value)
                    elif isinstance(field, QDoubleSpinBox):
                        field.setValue(value)
                    elif isinstance(field, QDateEdit):
                        field.setDate(value)
                    elif isinstance(field, QComboBox):
                        field.setCurrentText(value)
                    elif isinstance(field, QTextEdit):
                        field.setPlainText(value)
                dialog.accept()
                return int(dialog.result())

            with patch.object(EntryDialog, "exec", accept_form):
                window.open_expense()
                self.assertEqual(len(window.state["expenses"]), 1)
                expense_id = window.state["expenses"][0]["id"]
                window.open_expense(expense_id)
                self.assertEqual(window.state["expenses"][0]["title"], "Dinner")
                window.open_goal()
                goal_id = window.state["goals"][0]["id"]
                window.open_quick_contribution()
                goal = window.state["goals"][0]
                today_text = QDate.currentDate().toString("yyyy-MM-dd")
                self.assertEqual(goal["entries"][today_text]["amount"], 250)
                window.open_debt()
                debt_id = window.state["debts"][0]["id"]
                window.open_payment(debt_id)
                self.assertEqual(window.state["debts"][0]["payments"][0]["amount"], 100)
                self.assertEqual(storage.load()["debts"][0]["payments"][0]["amount"], 100)

            with patch("app.ui.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
                window.delete_expense(expense_id)
            self.assertEqual(window.state["expenses"], [])
            window._undo_delete()
            self.assertEqual(window.state["expenses"][0]["title"], "Dinner")
            with patch("app.ui.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
                window.delete_debt(debt_id)
            self.assertEqual(window.state["debts"], [])
            window._undo_delete()
            self.assertEqual(len(window.state["debts"]), 1)
            with patch("app.ui.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
                window.delete_goal(goal_id)
            self.assertEqual(window.state["goals"], [])
            window._undo_delete()
            self.assertEqual(len(storage.load()["goals"]), 1)
            window.close()


if __name__ == "__main__":
    unittest.main()
