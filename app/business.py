from __future__ import annotations

import calendar
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any
from uuid import uuid4


CATEGORIES = [
    "Food", "Transport", "School", "Shopping", "Entertainment",
    "Subscriptions", "Utilities", "Healthcare", "Miscellaneous",
]
PAYMENT_METHODS = ["Cash", "GCash", "Bank", "Credit Card", "Other"]
CURRENCIES = [
    ("₱", "PHP"), ("$", "USD"), ("€", "EUR"), ("¥", "JPY"), ("£", "GBP"),
    ("A$", "AUD"), ("C$", "CAD"), ("Fr", "CHF"), ("CN¥", "CNY"), ("₹", "INR"),
    ("₩", "KRW"), ("S$", "SGD"), ("HK$", "HKD"), ("NZ$", "NZD"), ("฿", "THB"),
    ("Rp", "IDR"), ("RM", "MYR"), ("₫", "VND"), ("R$", "BRL"), ("Mex$", "MXN"),
    ("R", "ZAR"),
]


def new_id() -> str:
    return uuid4().hex


def today() -> date:
    return date.today()


def parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def date_text(value: date | str) -> str:
    return parse_date(value).isoformat()


def money(value: float, state: dict[str, Any]) -> str:
    symbol = state.get("settings", {}).get("currency", "₱")
    amount = float(value or 0)
    sign = "-" if amount < 0 else ""
    return f"{sign}{symbol}{abs(amount):,.2f}"


def defaults() -> dict[str, Any]:
    return {
        "settings": {"currency": "₱", "theme": "dark"},
        "categories": CATEGORIES.copy(),
        "goals": [],
        "expenses": [],
        "budgetConfig": {"type": "monthly", "amount": 8000},
        "debts": [],
        "activity": [],
        "deleted": [],
    }


def validate_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("The data file must contain a JSON object.")
    state = defaults()
    state.update(value)
    if not isinstance(state.get("settings"), dict):
        raise ValueError("Settings must be an object.")
    state["settings"] = {**defaults()["settings"], **state["settings"]}
    if not isinstance(state["settings"].get("currency"), str):
        raise ValueError("Currency must be text.")
    if not isinstance(state["settings"].get("theme"), str):
        raise ValueError("Theme must be text.")
    for key in ("categories", "goals", "expenses", "debts", "activity", "deleted"):
        if not isinstance(state.get(key), list):
            raise ValueError(f"{key} must be a list.")
    cfg = state.get("budgetConfig")
    if not isinstance(cfg, dict):
        raise ValueError("Budget configuration must be an object.")
    cfg = {**defaults()["budgetConfig"], **cfg}
    if cfg.get("type") not in {"weekly", "monthly", "yearly", "custom"}:
        raise ValueError("Budget type is invalid.")
    cfg["amount"] = _number(cfg.get("amount"), "Budget amount", minimum=0)
    if cfg["type"] == "custom":
        _date_required(cfg.get("customStart"), "Custom budget start")
        _date_required(cfg.get("customEnd"), "Custom budget end")
        if cfg["customStart"] > cfg["customEnd"]:
            raise ValueError("Custom budget start must be on or before its end.")
    state["budgetConfig"] = cfg

    categories = state["categories"]
    if any(not isinstance(item, str) or not item.strip() for item in categories):
        raise ValueError("Categories must be non-empty text.")
    if len(set(categories)) != len(categories):
        raise ValueError("Categories must be unique.")

    ids: set[str] = set()
    for key in ("goals", "expenses", "debts"):
        for record in state[key]:
            if not isinstance(record, dict):
                raise ValueError(f"Every {key[:-1]} must be an object.")
            record_id = record.get("id")
            if not isinstance(record_id, str) or not record_id:
                raise ValueError(f"Every {key[:-1]} must have an ID.")
            if record_id in ids:
                raise ValueError("Record IDs must be unique.")
            ids.add(record_id)

    for goal in state["goals"]:
        _required_text(goal.get("name"), "Goal name")
        goal["target"] = _number(goal.get("target"), "Goal target", minimum=0, exclusive=True)
        _date_required(goal.get("startDate"), "Goal start date")
        _date_required(goal.get("targetDate"), "Goal target date")
        if goal["targetDate"] < goal["startDate"]:
            raise ValueError("Goal target date must be on or after its start date.")
        if goal.get("method") not in {"daily", "weekly", "biweekly", "monthly", "custom"}:
            raise ValueError("Goal saving method is invalid.")
        goal["customDays"] = _number(goal.get("customDays", 7), "Custom interval", minimum=1)
        if not isinstance(goal.get("entries", {}), dict):
            raise ValueError("Goal contribution entries must be an object.")
        for entry_date, entry in goal.get("entries", {}).items():
            _date_required(entry_date, "Contribution date")
            if not isinstance(entry, dict) or entry.get("status") not in {
                "completed", "partial", "missed", "skip",
            }:
                raise ValueError("A contribution has an invalid status.")
            entry["amount"] = _number(entry.get("amount", 0), "Contribution amount", minimum=0)
            entry["notes"] = str(entry.get("notes", ""))

    for expense in state["expenses"]:
        _required_text(expense.get("title"), "Expense title")
        expense["amount"] = _number(expense.get("amount"), "Expense amount", minimum=0, exclusive=True)
        _date_required(expense.get("date"), "Expense date")
        _required_text(expense.get("category"), "Expense category")
        _required_text(expense.get("method"), "Payment method")
        expense["notes"] = str(expense.get("notes", ""))

    for debt in state["debts"]:
        _required_text(debt.get("borrower"), "Debt contact")
        debt["amount"] = _number(debt.get("amount"), "Debt amount", minimum=0, exclusive=True)
        debt["rate"] = _number(debt.get("rate", 0), "Interest rate", minimum=0)
        _date_required(debt.get("dateBorrowed"), "Debt start date")
        _date_required(debt.get("dueDate"), "Debt due date")
        if debt.get("direction") not in {"owed-to-me", "i-owe"}:
            raise ValueError("Debt direction is invalid.")
        if debt.get("interestType") not in {"none", "simple", "compound"}:
            raise ValueError("Debt interest type is invalid.")
        if debt.get("interestFreq") not in {"daily", "weekly", "monthly", "yearly"}:
            raise ValueError("Debt interest frequency is invalid.")
        if debt.get("status") not in {"active", "paid", "overdue"}:
            raise ValueError("Debt status is invalid.")
        payments = debt.setdefault("payments", [])
        if not isinstance(payments, list):
            raise ValueError("Debt payments must be a list.")
        for payment in payments:
            if not isinstance(payment, dict):
                raise ValueError("Every payment must be an object.")
            payment["amount"] = _number(payment.get("amount"), "Payment amount", minimum=0, exclusive=True)
            _date_required(payment.get("date"), "Payment date")

    return state


def _number(value: Any, label: str, minimum: float, exclusive: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a number.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number.") from None
    if number != number or abs(number) == float("inf"):
        raise ValueError(f"{label} must be finite.")
    if number < minimum or (exclusive and number == minimum):
        relation = "greater than" if exclusive else "at least"
        raise ValueError(f"{label} must be {relation} {minimum:g}.")
    return number


def _date_required(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} is required.")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError(f"{label} is not a valid date.") from None


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required.")
    return value.strip()


def period_range(state: dict[str, Any], current: date | None = None) -> tuple[date, date]:
    now = current or today()
    cfg = state["budgetConfig"]
    if cfg["type"] == "weekly":
        start = now - timedelta(days=(now.weekday() + 1) % 7)
        return start, start + timedelta(days=6)
    if cfg["type"] == "yearly":
        return date(now.year, 1, 1), date(now.year, 12, 31)
    if cfg["type"] == "custom" and cfg.get("customStart") and cfg.get("customEnd"):
        return parse_date(cfg["customStart"]), parse_date(cfg["customEnd"])
    return date(now.year, now.month, 1), date(now.year, now.month, calendar.monthrange(now.year, now.month)[1])


def spent_in_range(state: dict[str, Any], start: date, end: date) -> float:
    return sum(e["amount"] for e in state["expenses"] if start <= parse_date(e["date"]) <= end)


def daily_totals(state: dict[str, Any]) -> dict[str, float]:
    result: dict[str, float] = defaultdict(float)
    for expense in state["expenses"]:
        result[expense["date"]] += expense["amount"]
    return dict(result)


def category_totals(state: dict[str, Any]) -> dict[str, float]:
    result: dict[str, float] = defaultdict(float)
    for expense in state["expenses"]:
        result[expense["category"]] += expense["amount"]
    return dict(result)


def average_daily_spending(state: dict[str, Any], current: date | None = None) -> float:
    expenses = state["expenses"]
    if not expenses:
        return 0
    first = min(parse_date(e["date"]) for e in expenses)
    return sum(e["amount"] for e in expenses) / max(1, ((current or today()) - first).days + 1)


def budget_health(state: dict[str, Any], current: date | None = None) -> int:
    start, end = period_range(state, current)
    spent = spent_in_range(state, start, end)
    budget = state["budgetConfig"]["amount"] or 1
    ratio = spent / budget
    score = 100 - ratio * 35 if ratio <= 1 else max(0, 65 - (ratio - 1) * 90)
    return math.floor(max(0, min(100, score)) + 0.5)


def projected_budget(state: dict[str, Any], current: date | None = None) -> float:
    now = current or today()
    start, end = period_range(state, now)
    elapsed = max(1, min((now - start).days + 1, (end - start).days + 1))
    return spent_in_range(state, start, end) / elapsed * ((end - start).days + 1)


def saved_amount(goal: dict[str, Any]) -> float:
    return sum(
        entry.get("amount", 0)
        for entry in goal.get("entries", {}).values()
        if entry.get("status") in {"completed", "partial"}
    )


def goal_progress(goal: dict[str, Any]) -> float:
    return min(999, saved_amount(goal) / goal["target"] * 100) if goal["target"] > 0 else 0


def goal_period_days(goal: dict[str, Any]) -> int:
    return {
        "daily": 1, "weekly": 7, "biweekly": 14, "monthly": 30,
    }.get(goal["method"], int(goal.get("customDays") or 7))


def goal_contributions(goal: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return sorted(
        ((d, e) for d, e in goal.get("entries", {}).items()
         if e.get("status") in {"completed", "partial"}),
        key=lambda item: item[0],
    )


def goal_average(goal: dict[str, Any]) -> float:
    entries = goal_contributions(goal)
    return sum(e.get("amount", 0) for _, e in entries) / len(entries) if entries else 0


def goal_total_periods(goal: dict[str, Any]) -> int:
    days = (parse_date(goal["targetDate"]) - parse_date(goal["startDate"])).days
    return max(1, (days + goal_period_days(goal) - 1) // goal_period_days(goal))


def goal_elapsed_periods(goal: dict[str, Any], current: date | None = None) -> int:
    elapsed = max(0, ((current or today()) - parse_date(goal["startDate"])).days)
    return max(1, elapsed // goal_period_days(goal) + 1)


def goal_success_rate(goal: dict[str, Any], current: date | None = None) -> float:
    rate = min(1, len(goal_contributions(goal)) / goal_elapsed_periods(goal, current))
    return rate or 0.0001


def goal_estimated_completion(goal: dict[str, Any], current: date | None = None) -> date | None:
    now = current or today()
    average = goal_average(goal) or goal["target"] / goal_total_periods(goal)
    if average <= 0:
        return None
    remaining = max(0, goal["target"] - saved_amount(goal))
    periods = math.ceil(remaining / average)
    return now + timedelta(days=periods * goal_period_days(goal))


def goal_projected_if_misses(goal: dict[str, Any], current: date | None = None) -> date | None:
    now = current or today()
    estimated = goal_estimated_completion(goal, now)
    if estimated is None:
        return None
    days = (estimated - now).days
    rate = goal_success_rate(goal, now)
    projected_days = math.ceil(days / rate)
    return now + timedelta(days=projected_days)


def goal_longest_streak(goal: dict[str, Any]) -> int:
    dates = [parse_date(d) for d, _ in goal_contributions(goal)]
    longest = run = 0
    previous: date | None = None
    for current in dates:
        run = run + 1 if previous and (current - previous).days == 1 else 1
        longest = max(longest, run)
        previous = current
    return longest


def goal_current_streak(goal: dict[str, Any], current: date | None = None) -> int:
    now = current or today()
    entries = goal.get("entries", {})
    entry_today = entries.get(now.isoformat())
    if not entry_today or entry_today.get("status") not in {"completed", "partial"}:
        now -= timedelta(days=1)
    streak = 0
    while (entry := entries.get(now.isoformat())) and entry.get("status") in {"completed", "partial"}:
        streak += 1
        now -= timedelta(days=1)
    return streak


def debt_interest(debt: dict[str, Any], current: date | None = None) -> float:
    if debt["interestType"] == "none" or not debt["rate"]:
        return 0
    period_days = {"daily": 1, "weekly": 7, "monthly": 30, "yearly": 365}[debt["interestFreq"]]
    elapsed = max(0, ((current or today()) - parse_date(debt["dateBorrowed"])).days) / period_days
    rate = debt["rate"] / 100
    if debt["interestType"] == "compound":
        return debt["amount"] * ((1 + rate) ** elapsed - 1)
    return debt["amount"] * rate * elapsed


def debt_paid(debt: dict[str, Any]) -> float:
    return sum(p["amount"] for p in debt.get("payments", []))


def debt_collectable(debt: dict[str, Any], current: date | None = None) -> float:
    return debt["amount"] + debt_interest(debt, current)


def debt_owed(debt: dict[str, Any], current: date | None = None) -> float:
    return max(0, debt_collectable(debt, current) - debt_paid(debt)) if debt["status"] != "paid" else 0


def debt_overdue_days(debt: dict[str, Any], current: date | None = None) -> int:
    if debt["status"] == "paid":
        return 0
    return max(0, ((current or today()) - parse_date(debt["dueDate"])).days)


def debt_status(debt: dict[str, Any], current: date | None = None) -> str:
    if debt["status"] == "paid":
        return "paid"
    return "overdue" if debt_overdue_days(debt, current) else "active"


def analytics(state: dict[str, Any], current: date | None = None) -> dict[str, Any]:
    now = current or today()
    saved = sum(saved_amount(g) for g in state["goals"])
    spent = sum(e["amount"] for e in state["expenses"])
    owed_to_you = sum(debt_owed(d, now) for d in state["debts"] if d["direction"] != "i-owe")
    you_owe = sum(debt_owed(d, now) for d in state["debts"] if d["direction"] == "i-owe")
    cfg = state["budgetConfig"]
    projected = projected_budget(state, now)
    accuracy = max(0, min(100, 100 - abs(projected - cfg["amount"]) / cfg["amount"] * 100)) if cfg["amount"] else 0
    collectable = [d for d in state["debts"] if d["direction"] != "i-owe"]
    total_collectable = sum(debt_collectable(d, now) for d in collectable)
    collection_rate = sum(debt_paid(d) for d in collectable) / total_collectable * 100 if total_collectable else 0
    total = saved + spent
    avg_weekly_savings = sum(goal_average(g) for g in state["goals"])
    days_left = (date(now.year, 12, 31) - now).days
    daily_rate = sum(goal_average(g) / goal_period_days(g) for g in state["goals"])
    return {
        "saved": saved, "spent": spent, "net": saved - spent,
        "owed_to_you": owed_to_you, "you_owe": you_owe,
        "net_debt": owed_to_you - you_owe,
        "savings_rate": saved / total * 100 if total else 0,
        "budget_accuracy": accuracy, "collection_rate": collection_rate,
        "health": budget_health(state, now), "avg_weekly_savings": avg_weekly_savings,
        "avg_monthly_spending": average_daily_spending(state, now) * 30,
        "savings_consistency": (
            sum(goal_success_rate(g, now) for g in state["goals"])
            / len(state["goals"]) * 100 if state["goals"] else 0
        ),
        "longest_streak": max((goal_longest_streak(g) for g in state["goals"]), default=0),
        "year_end_savings": saved + daily_rate * days_left,
        "projected_collection": sum(
            debt_owed(d, now) for d in state["debts"]
            if d["direction"] != "i-owe" and d["status"] != "paid"
        ),
        "projected_budget": projected,
        "monthly_spend": monthly_spend_series(state, now),
        "category_totals": category_totals(state),
        "heatmap": contribution_heatmap(state),
        "insights": insights(state, now),
    }


def monthly_spend_series(state: dict[str, Any], current: date | None = None) -> list[tuple[str, float]]:
    now = current or today()
    series: list[tuple[str, float]] = []
    for offset in range(5, -1, -1):
        month_index = now.month - 1 - offset
        year = now.year + month_index // 12
        month = month_index % 12 + 1
        start = date(year, month, 1)
        end = date(year, month, calendar.monthrange(year, month)[1])
        series.append((start.strftime("%b"), spent_in_range(state, start, end)))
    return series


def contribution_heatmap(state: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = defaultdict(int)
    for goal in state["goals"]:
        for day, entry in goal.get("entries", {}).items():
            if entry.get("status") in {"completed", "partial"}:
                result[day] += 1
    return dict(result)


def insights(state: dict[str, Any], current: date | None = None) -> list[str]:
    now = current or today()
    messages: list[str] = []
    this_total = spent_in_range(state, date(now.year, now.month, 1), now)
    prev_month = date(now.year, now.month, 1) - timedelta(days=1)
    last_total = spent_in_range(
        state, date(prev_month.year, prev_month.month, 1), prev_month,
    )
    if last_total > 0:
        diff = (this_total - last_total) / last_total * 100
        messages.append(
            f"You are {abs(diff):.0f}% {'under' if diff <= 0 else 'over'} last month's spending pace."
        )
    active = [g for g in state["goals"] if goal_progress(g) < 100]
    if active:
        goal = min(active, key=lambda g: g["targetDate"])
        estimated = goal_estimated_completion(goal, now)
        if estimated:
            diff_days = (parse_date(goal["targetDate"]) - estimated).days
            if diff_days > 0:
                messages.append(f'You are on track to reach "{goal["name"]}" {diff_days} day(s) early.')
            elif diff_days < 0:
                messages.append(f'At current pace, "{goal["name"]}" may finish {abs(diff_days)} day(s) late.')
    start, end = period_range(state, now)
    spent = spent_in_range(state, start, end)
    if spent > state["budgetConfig"]["amount"]:
        messages.append(
            f'You exceeded your {state["budgetConfig"]["type"]} budget by '
            f'{money(spent - state["budgetConfig"]["amount"], state)}.'
        )
    categories = category_totals(state)
    if categories:
        name, amount = max(categories.items(), key=lambda item: item[1])
        messages.append(f"{name} is your top spending category at {money(amount, state)}.")
    return messages or ["Add more expenses and goal contributions to unlock personalized insights."]


def activity(state: dict[str, Any], text: str, kind: str = "info") -> None:
    state["activity"].insert(0, {"id": new_id(), "text": text, "type": kind, "ts": datetime.now().timestamp()})
    del state["activity"][60:]
