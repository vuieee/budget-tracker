from __future__ import annotations

import unittest
from datetime import date

from app import business as logic


class BusinessLogicTests(unittest.TestCase):
    def test_budget_period_totals_and_projection(self) -> None:
        state = logic.defaults()
        state["budgetConfig"] = {
            "type": "custom", "amount": 1000,
            "customStart": "2025-01-01", "customEnd": "2025-01-31",
        }
        state["expenses"] = [
            {"id": "a", "title": "A", "date": "2025-01-02", "amount": 100, "category": "Food", "method": "Cash"},
            {"id": "b", "title": "B", "date": "2025-01-11", "amount": 50, "category": "Food", "method": "Bank"},
            {"id": "c", "title": "C", "date": "2024-12-31", "amount": 70, "category": "Food", "method": "Cash"},
        ]
        state = logic.validate_state(state)
        self.assertEqual(logic.spent_in_range(state, date(2025, 1, 1), date(2025, 1, 31)), 150)
        self.assertAlmostEqual(logic.projected_budget(state, date(2025, 1, 11)), 150 / 11 * 31)
        self.assertEqual(logic.category_totals(state), {"Food": 220})

    def test_savings_counts_only_completed_and_partial_entries(self) -> None:
        goal = {
            "target": 1000, "method": "daily", "startDate": "2025-01-01",
            "targetDate": "2025-01-31",
            "entries": {
                "2025-01-01": {"amount": 100, "status": "completed"},
                "2025-01-02": {"amount": 50, "status": "partial"},
                "2025-01-03": {"amount": 500, "status": "missed"},
                "2025-01-04": {"amount": 300, "status": "skip"},
            },
        }
        self.assertEqual(logic.saved_amount(goal), 150)
        self.assertEqual(logic.goal_progress(goal), 15)
        self.assertEqual(logic.goal_longest_streak(goal), 2)

    def test_compound_interest_and_payment_balance(self) -> None:
        debt = {
            "amount": 1000, "rate": 12, "interestType": "compound", "interestFreq": "monthly",
            "dateBorrowed": "2025-01-01", "dueDate": "2025-12-31",
            "status": "active", "direction": "owed-to-me",
            "payments": [{"amount": 100, "date": "2025-01-15"}],
        }
        accrued = 1000 * ((1.12 ** (30 / 30)) - 1)
        self.assertAlmostEqual(logic.debt_interest(debt, date(2025, 1, 31)), accrued)
        self.assertAlmostEqual(logic.debt_owed(debt, date(2025, 1, 31)), 1000 + accrued - 100)

    def test_health_score_and_analytics_totals(self) -> None:
        state = logic.defaults()
        state["budgetConfig"]["amount"] = 100
        state["expenses"] = [
            {"id": "e1", "title": "Test", "date": "2025-06-05", "amount": 50, "category": "Food", "method": "Cash"},
        ]
        state = logic.validate_state(state)
        self.assertEqual(logic.budget_health(state, date(2025, 6, 10)), 83)
        summary = logic.analytics(state, date(2025, 6, 10))
        self.assertEqual(summary["spent"], 50)
        self.assertEqual(summary["net"], -50)
        self.assertEqual(summary["health"], 83)

    def test_invalid_data_is_rejected(self) -> None:
        state = logic.defaults()
        state["expenses"] = [{
            "id": "e1", "title": "Bad", "date": "not-a-date", "amount": 12,
            "category": "Food", "method": "Cash",
        }]
        with self.assertRaisesRegex(ValueError, "Expense date"):
            logic.validate_state(state)


if __name__ == "__main__":
    unittest.main()
