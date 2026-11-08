from __future__ import annotations

import copy
import calendar
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QAction, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QAbstractSpinBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QGroupBox, QLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QToolButton, QVBoxLayout, QWidget,
)

from . import business as logic
from .storage import BudgetStorage, StorageError


BG = "#262626"
RAISED = "#30302f"
CARD = "#30302f"
LINE = "#595959"
FG = "#f0f1f2"
DIM = "#d9d3c7"
FAINT = "#aaa89e"
ACCENT = "#d9d3c7"
OK = "#b9c3a0"
WARN = "#e4cc99"
RED = "#efaaa6"
BLUE = "#83b9e8"


def button(text: str, callback: Callable[[], None], primary: bool = False, danger: bool = False) -> QPushButton:
    result = QPushButton(text)
    result.setProperty("primary", primary)
    result.setProperty("danger", danger)
    result.clicked.connect(callback)
    return result


def label(text: str, style: str = "normal") -> QLabel:
    result = QLabel(text)
    result.setWordWrap(True)
    result.setProperty("role", style)
    return result


def money(value: float, state: dict[str, Any]) -> str:
    return logic.money(value, state)


def date_edit(value: str | None = None, allow_empty: bool = False) -> QDateEdit:
    widget = QDateEdit()
    widget.setCalendarPopup(True)
    widget.setDisplayFormat("yyyy-MM-dd")
    if allow_empty:
        widget.setMinimumDate(QDate(1900, 1, 1))
        widget.setSpecialValueText("Choose date")
    widget.setDate(
        QDate.fromString(value, "yyyy-MM-dd")
        if value else (widget.minimumDate() if allow_empty else QDate.currentDate())
    )
    return widget


def iso_date(widget: QDateEdit) -> str:
    if widget.date() == widget.minimumDate() and widget.specialValueText():
        return ""
    return widget.date().toString("yyyy-MM-dd")


class ChartWidget(QWidget):
    def __init__(self, kind: str, labels: list[str], values: list[float], second: list[float] | None = None):
        super().__init__()
        self.kind, self.labels, self.values, self.second = kind, labels, values, second
        self.setMinimumHeight(190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event: Any) -> None:
        from PySide6.QtGui import QPainter, QPen, QBrush

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        rect = self.rect().adjusted(12, 12, -12, -28)
        if not self.values:
            painter.setPen(Qt.GlobalColor.gray)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No data")
            return
        max_value = max([*self.values, *(self.second or [])], default=0) or 1
        count = len(self.values)
        slot = rect.width() / max(1, count)
        painter.setPen(QPen(Qt.GlobalColor.darkGray, 1))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
        if self.kind == "donut":
            colors = ["#d9d3c7", "#83b9e8", "#b9c3a0", "#d98a86", "#d8b17f", "#c5b7d9"]
            total = sum(max(0, v) for v in self.values) or 1
            start = 0
            diameter = min(rect.height(), 150)
            ring = rect.adjusted((rect.width() - diameter) / 2, 0, -(rect.width() - diameter) / 2, 0)
            for index, value in enumerate(self.values):
                span = round(5760 * max(0, value) / total)
                painter.setPen(QPen(QColor(colors[index % len(colors)]), 22))
                painter.drawArc(ring.adjusted(16, 16, -16, -16), start, span)
                start += span
            return
        for index, value in enumerate(self.values):
            height = rect.height() * max(0, value) / max_value
            if self.kind == "line":
                x = int(rect.left() + slot * (index + 0.5))
                y = int(rect.bottom() - height)
                if index:
                    old_h = rect.height() * max(0, self.values[index - 1]) / max_value
                    painter.setPen(QPen(QColor(BLUE), 2))
                    painter.drawLine(
                        int(rect.left() + slot * (index - 0.5)), int(rect.bottom() - old_h), x, y,
                    )
                painter.setBrush(QBrush(QColor(FG)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(x - 3, y - 3, 6, 6)
            else:
                bar_w = max(4, int(slot * (0.56 if not self.second else 0.25)))
                h = int(height)
                if self.second:
                    second_h = int(rect.height() * max(0, self.second[index]) / max_value)
                    painter.fillRect(
                        int(rect.left() + slot * index + slot * 0.2), rect.bottom() - h,
                        bar_w, h, QColor(FG),
                    )
                    painter.fillRect(
                        int(rect.left() + slot * index + slot * 0.53), rect.bottom() - second_h,
                        bar_w, second_h, QColor(BLUE),
                    )
                else:
                    painter.fillRect(
                        int(rect.left() + slot * index + (slot - bar_w) / 2),
                        rect.bottom() - h, bar_w, h, QColor(FG),
                    )
        painter.setPen(QColor(FAINT))
        for index, text in enumerate(self.labels):
            painter.drawText(
                int(rect.left() + slot * index), rect.bottom() + 6, int(slot), 18,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, text,
            )


class EntryDialog(QDialog):
    def __init__(self, title: str, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.fields: dict[str, QWidget] = {}
        self.form = QFormLayout()
        self.form.setSpacing(12)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(self.form)
        layout.addWidget(self.buttons)

    def add_text(self, key: str, title: str, value: str = "", placeholder: str = "") -> QLineEdit:
        widget = QLineEdit(value)
        widget.setPlaceholderText(placeholder)
        self.fields[key] = widget
        self.form.addRow(title, widget)
        return widget

    def add_amount(self, key: str, title: str, value: float | None = None, minimum: float = 0) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(minimum, 1_000_000_000_000)
        widget.setDecimals(2)
        widget.setSingleStep(1)
        widget.setGroupSeparatorShown(True)
        if value is not None:
            widget.setValue(value)
        self.fields[key] = widget
        self.form.addRow(title, widget)
        return widget

    def add_int(self, key: str, title: str, value: int = 1, minimum: int = 1) -> QSpinBox:
        widget = QSpinBox()
        widget.setRange(minimum, 36500)
        widget.setValue(value)
        self.fields[key] = widget
        self.form.addRow(title, widget)
        return widget

    def add_date(self, key: str, title: str, value: str | None = None, allow_empty: bool = False) -> QDateEdit:
        widget = date_edit(value, allow_empty)
        self.fields[key] = widget
        self.form.addRow(title, widget)
        return widget

    def add_combo(self, key: str, title: str, values: list[str], selected: str | None = None) -> QComboBox:
        widget = QComboBox()
        widget.addItems(values)
        if selected in values:
            widget.setCurrentText(selected)
        self.fields[key] = widget
        self.form.addRow(title, widget)
        return widget

    def add_notes(self, key: str, title: str, value: str = "") -> QTextEdit:
        widget = QTextEdit()
        widget.setPlainText(value)
        widget.setMaximumHeight(100)
        self.fields[key] = widget
        self.form.addRow(title, widget)
        return widget

    def value(self, key: str) -> Any:
        widget = self.fields[key]
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
            return widget.value()
        if isinstance(widget, QDateEdit):
            return iso_date(widget)
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QTextEdit):
            return widget.toPlainText().strip()
        raise TypeError(f"Unsupported form field: {key}")


class BudgetWindow(QMainWindow):
    TAB_NAMES = ["Dashboard", "Savings Goals", "Budget Tracker", "Debt Tracker", "Analytics", "Settings"]

    def __init__(self, storage: BudgetStorage):
        super().__init__()
        self.storage = storage
        self.state = storage.load()
        self.current_goal_id: str | None = None
        self.expense_filters = {"category": "All Categories", "method": "All Methods", "from": "", "to": ""}
        self.calendar_view = "month"
        self.calendar_cursor = date.today().replace(day=1)
        self._building_search = False
        self.setWindowTitle("Budget Tracker")
        self.resize(1120, 820)
        self.setMinimumSize(820, 600)
        self._make_ui()
        self.render_all()

    def _make_ui(self) -> None:
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(26, 20, 26, 14)
        outer.setSpacing(12)
        title_row = QHBoxLayout()
        title_row.addWidget(label("Budget Tracker", "title"))
        title_row.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search goals, expenses, debt, notes…  ( / )")
        self.search.setMaximumWidth(420)
        self.search.textChanged.connect(self.search_changed)
        title_row.addWidget(self.search)
        self.today_label = label(date.today().strftime("%A, %B %d, %Y"), "dim")
        title_row.addWidget(self.today_label)
        self.save_label = label("Saved", "dim")
        title_row.addWidget(self.save_label)
        add_button = QToolButton()
        add_button.setText("+ Add")
        add_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.quick_add_button = add_button
        menu = QMenu(add_button)
        for text, callback in (
            ("Expense", self.open_expense), ("Savings Goal", self.open_goal),
            ("Debt Entry", self.open_debt), ("Contribution", self.open_quick_contribution),
        ):
            action = QAction(f"+ {text}", self)
            action.triggered.connect(callback)
            menu.addAction(action)
        add_button.setMenu(menu)
        title_row.addWidget(add_button)
        outer.addLayout(title_row)
        self.search_results = QWidget()
        self.search_results_layout = QVBoxLayout(self.search_results)
        self.search_results_layout.setContentsMargins(0, 0, 0, 0)
        self.search_results.hide()
        outer.addWidget(self.search_results)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.pages: list[QWidget] = []
        for name in self.TAB_NAMES:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            content = QWidget()
            content.setObjectName("tabContent")
            content_layout = QVBoxLayout(content)
            content_layout.setContentsMargins(6, 18, 6, 22)
            content_layout.setSpacing(14)
            content_layout.addStretch()
            scroll.setWidget(content)
            self.tabs.addTab(scroll, name)
            self.pages.append(content)
        self.tabs.currentChanged.connect(self.render_current)
        outer.addWidget(self.tabs, 1)
        self.storage_label = label(f"Local data: {self.storage.path}", "faint")
        self.storage_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(self.storage_label)
        self.setCentralWidget(root)
        self.undo_button = QPushButton("UNDO")
        self.undo_button.clicked.connect(self._undo_delete)
        self.undo_button.hide()
        self.statusBar().addPermanentWidget(self.undo_button)
        self._last_deleted: tuple[str, dict[str, Any]] | None = None
        self.setStyleSheet(self._style_for_theme(self.state["settings"].get("theme", "dark")))
        QShortcut(QKeySequence("/"), self, activated=self._focus_search)
        QShortcut(QKeySequence("Q"), self, activated=self._open_quick_add)
        for key, index in enumerate(range(6), 1):
            QShortcut(QKeySequence(str(key)), self, activated=lambda i=index: self._shortcut_nav(i))

    @staticmethod
    def _style() -> str:
        return f"""
        QWidget {{ background: {BG}; color: {FG}; font-family: Consolas, 'Courier New', monospace; font-size: 12px; }}
        QMainWindow {{ background: {BG}; }}
        QLabel[role="title"] {{ font-size: 23px; font-weight: 600; }}
        QLabel[role="section"] {{ font-size: 19px; font-weight: 600; }}
        QLabel[role="subtitle"], QLabel[role="dim"] {{ color: {DIM}; }}
        QLabel[role="faint"] {{ color: {FAINT}; font-size: 10px; }}
        QLabel[role="cardLabel"] {{ color: {FAINT}; font-size: 10px; letter-spacing: 1px; }}
        QLabel[role="value"] {{ font-size: 22px; font-weight: 600; }}
        QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox, QTextEdit {{
          background: {RAISED}; color: {FG}; border: 1px solid {LINE}; padding: 8px; selection-background-color: {BLUE};
        }}
        QComboBox QAbstractItemView {{ background: {RAISED}; selection-background-color: {LINE}; }}
        QPushButton, QToolButton {{
          background: #3a3b39; color: {FG}; border: 1px solid {LINE}; padding: 8px 12px;
        }}
        QPushButton:hover, QToolButton:hover {{ background: #4a4b49; }}
        QPushButton[primary="true"], QToolButton {{ background: {DIM}; color: {BG}; font-weight: 600; }}
        QPushButton[danger="true"] {{ color: {RED}; }}
        QTabWidget::pane {{ border: 1px solid {LINE}; }}
        QTabBar::tab {{ background: {BG}; border: 1px solid {LINE}; padding: 10px 14px; }}
        QTabBar::tab:selected {{ background: #3a3b39; border-bottom: 2px solid {DIM}; }}
        QScrollArea {{ border: none; }}
        QFrame[role="card"] {{ background: {CARD}; border: 1px solid {LINE}; }}
        QGroupBox {{ border: 1px solid {LINE}; margin-top: 10px; padding: 10px; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 10px; color: {FAINT}; }}
        QTableWidget {{ background: {RAISED}; gridline-color: {LINE}; selection-background-color: #4a4b49; }}
        QHeaderView::section {{ background: #3a3b39; color: {DIM}; border: none; padding: 7px; }}
        QProgressBar {{ border: 1px solid {LINE}; background: #3a3b39; height: 7px; text-align: center; }}
        QProgressBar::chunk {{ background: {DIM}; }}
        QMenu {{ background: {RAISED}; border: 1px solid {LINE}; }}
        QMenu::item:selected {{ background: #4a4b49; }}
        """

    def page_layout(self, index: int) -> QVBoxLayout:
        layout = self.pages[index].layout()
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
        layout.insertStretch(0, 1)
        layout.removeItem(layout.itemAt(0))
        return layout

    @staticmethod
    def _clear_layout(layout: QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                BudgetWindow._clear_layout(item.layout())

    def _add_top(self, layout: QVBoxLayout, title: str, subtitle: str = "", actions: list[QWidget] | None = None) -> None:
        row = QHBoxLayout()
        box = QVBoxLayout()
        box.addWidget(label(title, "section"))
        if subtitle:
            box.addWidget(label(subtitle, "faint"))
        row.addLayout(box)
        row.addStretch()
        for widget in actions or []:
            row.addWidget(widget)
        layout.addLayout(row)

    def _card(self, title: str, value: str, subtitle: str = "") -> QFrame:
        frame = QFrame()
        frame.setProperty("role", "card")
        box = QVBoxLayout(frame)
        box.setContentsMargins(14, 12, 14, 12)
        box.addWidget(label(title.upper(), "cardLabel"))
        box.addWidget(label(value, "value"))
        if subtitle:
            box.addWidget(label(subtitle, "faint"))
        frame.setMinimumWidth(130)
        return frame

    def _metric_grid(self, layout: QVBoxLayout, items: list[tuple[str, str, str]]) -> None:
        grid = QGridLayout()
        grid.setSpacing(12)
        columns = 4 if len(items) >= 4 else max(1, len(items))
        for index, (title, value, subtitle) in enumerate(items):
            grid.addWidget(self._card(title, value, subtitle), index // columns, index % columns)
        layout.addLayout(grid)

    def _chart(self, layout: QVBoxLayout, title: str, kind: str, labels: list[str], values: list[float], second: list[float] | None = None) -> None:
        group = QGroupBox(title)
        box = QVBoxLayout(group)
        box.addWidget(ChartWidget(kind, labels, values, second))
        layout.addWidget(group)

    def _save_state(self, candidate: dict[str, Any]) -> bool:
        try:
            candidate = logic.validate_state(candidate)
            self.storage.save(candidate)
        except (ValueError, StorageError) as error:
            QMessageBox.critical(self, "Could not save data", str(error))
            return False
        self.state = candidate
        self.save_label.setText("Saved")
        self.render_all()
        return True

    def _change(self, operation: Callable[[dict[str, Any]], None]) -> bool:
        candidate = copy.deepcopy(self.state)
        operation(candidate)
        return self._save_state(candidate)

    def _open_quick_add(self) -> None:
        if not self._focus_is_editor():
            self.quick_add_button.showMenu()

    def _focus_search(self) -> None:
        if not self._focus_is_editor():
            self.search.setFocus()

    def _shortcut_nav(self, index: int) -> None:
        if not self._focus_is_editor():
            self.tabs.setCurrentIndex(index)

    def _focus_is_editor(self) -> bool:
        focus = QApplication.focusWidget()
        return isinstance(focus, (QLineEdit, QTextEdit, QComboBox, QAbstractSpinBox))

    def _show_undo(self, record_type: str, record: dict[str, Any]) -> None:
        self._last_deleted = (record_type, copy.deepcopy(record))
        self.statusBar().showMessage(f'{record_type.title()} deleted.')
        self.undo_button.show()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(5000, self.undo_button.hide)

    def _undo_delete(self) -> None:
        if not self._last_deleted:
            return
        record_type, record = self._last_deleted
        candidate = copy.deepcopy(self.state)
        collection = {"goal": "goals", "expense": "expenses", "debt": "debts"}[record_type]
        candidate[collection].append(record)
        candidate["deleted"] = [
            item for item in candidate["deleted"]
            if not (item.get("type") == record_type and item.get("data", {}).get("id") == record.get("id"))
        ]
        if self._save_state(candidate):
            self._last_deleted = None
            self.undo_button.hide()

    def render_all(self) -> None:
        self.render_dashboard()
        self.render_savings()
        self.render_budget()
        self.render_debts()
        self.render_analytics()
        self.render_settings()

    def render_current(self, index: int) -> None:
        renderers = [
            self.render_dashboard, self.render_savings, self.render_budget,
            self.render_debts, self.render_analytics, self.render_settings,
        ]
        if 0 <= index < len(renderers):
            renderers[index]()

    def render_dashboard(self) -> None:
        layout = self.page_layout(0)
        now = date.today()
        start, end = logic.period_range(self.state)
        remaining = self.state["budgetConfig"]["amount"] - logic.spent_in_range(self.state, start, end)
        debts = self.state["debts"]
        goal = min(
            (g for g in self.state["goals"] if logic.goal_progress(g) < 100),
            key=lambda g: g["targetDate"], default=None,
        )
        self._add_top(layout, "Dashboard", now.strftime("%B %Y · %A, %B %d"))
        quick = QHBoxLayout()
        for text, callback in (
            ("+ EXPENSE", self.open_expense), ("+ SAVE", self.open_quick_contribution),
            ("+ DEBT", self.open_debt),
        ):
            quick.addWidget(button(text, callback, primary=text == "+ EXPENSE"))
        quick.addStretch()
        layout.addLayout(quick)
        self._metric_grid(layout, [
            ("Current Savings", money(sum(logic.saved_amount(g) for g in self.state["goals"]), self.state), f"across {len(self.state['goals'])} goal(s)"),
            ("Remaining Budget", money(remaining, self.state), f"{self.state['budgetConfig']['type']} plan"),
            ("Owed to You", money(sum(logic.debt_owed(d) for d in debts if d["direction"] != "i-owe"), self.state),
             f"You owe {money(sum(logic.debt_owed(d) for d in debts if d['direction'] == 'i-owe'), self.state)} · "
             f"{sum(logic.debt_status(d) == 'overdue' for d in debts)} overdue"),
            ("Weekly / Monthly Spend", money(logic.spent_in_range(self.state, now - timedelta(days=(now.weekday() + 1) % 7), now), self.state),
             f"{money(logic.spent_in_range(self.state, now.replace(day=1), now), self.state)} this month"),
        ])
        health = logic.budget_health(self.state)
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(health)
        progress.setFormat(f"Budget health  {health}/100")
        layout.addWidget(progress)
        if goal:
            pct = int(logic.goal_progress(goal))
            goal_progress = QProgressBar()
            goal_progress.setRange(0, 100)
            goal_progress.setValue(min(100, pct))
            goal_progress.setFormat(f"Upcoming goal: {goal['name']}  {pct}%")
            layout.addWidget(goal_progress)
        else:
            layout.addWidget(label("No active savings goals. Create one from Savings Goals.", "dim"))
        week_dates = [now - timedelta(days=i) for i in range(6, -1, -1)]
        self._chart(layout, "7-Day Spending", "bar", [d.strftime("%a") for d in week_dates], [
            logic.spent_in_range(self.state, d, d) for d in week_dates
        ])
        recent = self.state["activity"][:8]
        if recent:
            table = self._table(["Recent activity", "Date"], [
                (str(item.get("text", "")), self._activity_date(item.get("ts", 0)))
                for item in recent
            ])
            layout.addWidget(table)
        else:
            layout.addWidget(label("No activity yet — start by adding an expense or goal.", "dim"))

    def render_savings(self) -> None:
        layout = self.page_layout(1)
        if self.current_goal_id and not any(g["id"] == self.current_goal_id for g in self.state["goals"]):
            self.current_goal_id = None
        if self.current_goal_id:
            self._render_goal_detail(layout)
            return
        goals = self.state["goals"]
        self._add_top(layout, "Savings Goals", f"{len(goals)} active goal(s)", [button("+ NEW GOAL", self.open_goal, True)])
        if not goals:
            layout.addWidget(label("No savings goals yet. Create one to track contributions on the calendar.", "dim"))
        grid = QGridLayout()
        for index, goal in enumerate(goals):
            pct = logic.goal_progress(goal)
            card = QFrame()
            card.setProperty("role", "card")
            content = QVBoxLayout(card)
            content.addWidget(label(goal["name"], "subtitle"))
            content.addWidget(label(money(logic.saved_amount(goal), self.state), "value"))
            content.addWidget(label(f"of {money(goal['target'], self.state)} target", "faint"))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(min(100, pct)))
            bar.setFormat(f"{pct:.0f}% · {goal['method'].upper()}")
            content.addWidget(bar)
            content.addWidget(label(f"Target {goal['targetDate']}", "faint"))
            content.addWidget(button("OPEN GOAL", lambda gid=goal["id"]: self._select_goal(gid)))
            grid.addWidget(card, index // 3, index % 3)
        layout.addLayout(grid)

    def _select_goal(self, goal_id: str | None) -> None:
        self.current_goal_id = goal_id
        self.render_savings()

    def _render_goal_detail(self, layout: QVBoxLayout) -> None:
        goal = next(g for g in self.state["goals"] if g["id"] == self.current_goal_id)
        pct = logic.goal_progress(goal)
        self._add_top(
            layout, goal["name"],
            f"{goal['startDate']} → {goal['targetDate']} · {goal['method'].upper()}",
            [
                button("< ALL GOALS", lambda: self._select_goal(None)),
                button("EDIT", lambda: self.open_goal(goal["id"])),
                button("DELETE", lambda: self.delete_goal(goal["id"]), danger=True),
            ],
        )
        days = max(0, (logic.parse_date(goal["targetDate"]) - date.today()).days)
        periods = max(1, (days + logic.goal_period_days(goal) - 1) // logic.goal_period_days(goal))
        remaining = max(0, goal["target"] - logic.saved_amount(goal))
        estimated = logic.goal_estimated_completion(goal)
        projected = logic.goal_projected_if_misses(goal)
        self._metric_grid(layout, [
            ("Saved", money(logic.saved_amount(goal), self.state), f"{pct:.1f}% complete"),
            ("Remaining", money(remaining, self.state), f"{days} days left"),
            ("Required / period", money(remaining / periods, self.state), goal["method"]),
            ("Est. completion", estimated.strftime("%b %d, %Y") if estimated else "—",
             f"if misses continue: {projected.strftime('%b %d, %Y')}" if projected else "—"),
            ("Longest streak", f"{logic.goal_longest_streak(goal)}d", ""),
            ("Avg contribution", money(logic.goal_average(goal), self.state), ""),
            ("Current streak", f"{logic.goal_current_streak(goal)}d", ""),
            ("Progress", f"{pct:.1f}%", ""),
        ])
        self._calendar_widget(layout, goal)

    def _calendar_widget(self, layout: QVBoxLayout, goal: dict[str, Any]) -> None:
        group = QGroupBox("Contribution Calendar")
        box = QVBoxLayout(group)
        controls = QHBoxLayout()
        view_combo = QComboBox()
        view_combo.addItems(["day", "week", "month", "year"])
        view_combo.setCurrentText(self.calendar_view)
        view_combo.currentTextChanged.connect(lambda value: self._set_calendar_view(value, goal))
        controls.addWidget(view_combo)
        controls.addWidget(button("<", lambda: self._shift_calendar(-1, goal)))
        self.calendar_title = label(self._calendar_title(), "subtitle")
        self.calendar_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls.addWidget(self.calendar_title, 1)
        controls.addWidget(button(">", lambda: self._shift_calendar(1, goal)))
        controls.addWidget(button("TODAY", lambda: self._calendar_today(goal)))
        box.addLayout(controls)
        self.calendar_grid = QGridLayout()
        self.calendar_grid.setSpacing(4)
        box.addLayout(self.calendar_grid)
        layout.addWidget(group)
        self._fill_calendar(goal)

    def _calendar_title(self) -> str:
        if self.calendar_view == "year":
            return str(self.calendar_cursor.year)
        if self.calendar_view == "day":
            return self.calendar_cursor.strftime("%b %d, %Y")
        if self.calendar_view == "week":
            start = self.calendar_cursor - timedelta(days=(self.calendar_cursor.weekday() + 1) % 7)
            return f"{start:%b %d} – {(start + timedelta(days=6)):%b %d, %Y}"
        return self.calendar_cursor.strftime("%B %Y")

    def _clear_calendar(self) -> None:
        while self.calendar_grid.count():
            item = self.calendar_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _fill_calendar(self, goal: dict[str, Any]) -> None:
        self._clear_calendar()
        self.calendar_title.setText(self._calendar_title())
        cursor = self.calendar_cursor
        if self.calendar_view == "year":
            for month in range(1, 13):
                count = sum(
                    1 for key, entry in goal.get("entries", {}).items()
                    if key.startswith(f"{cursor.year}-{month:02d}")
                    and entry.get("status") in {"completed", "partial"}
                )
                self.calendar_grid.addWidget(
                    button(f"{calendar.month_abbr[month].upper()}\n{count} saved", lambda m=month: self._open_calendar_month(m, goal)),
                    (month - 1) // 4, (month - 1) % 4,
                )
            return
        if self.calendar_view == "day":
            entry = goal.get("entries", {}).get(cursor.isoformat())
            text = "No entry" if not entry else f"{entry['status'].upper()} · {money(entry.get('amount', 0), self.state)}"
            self.calendar_grid.addWidget(label(f"{cursor:%A, %B %d, %Y}\n{text}"), 0, 0, 1, 7)
            self.calendar_grid.addWidget(button("OPEN DAY", lambda d=cursor: self.open_day(goal, d)), 1, 0, 1, 7)
            return
        weekdays = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
        for col, day_name in enumerate(weekdays):
            self.calendar_grid.addWidget(label(day_name, "faint"), 0, col)
        if self.calendar_view == "week":
            start = cursor - timedelta(days=(cursor.weekday() + 1) % 7)
            dates = [start + timedelta(days=i) for i in range(7)]
            offset = 0
        else:
            first = cursor.replace(day=1)
            offset = (first.weekday() + 1) % 7
            count = calendar.monthrange(cursor.year, cursor.month)[1]
            dates = [first + timedelta(days=i) for i in range(count)]
        for index, day in enumerate(dates):
            entry = goal.get("entries", {}).get(day.isoformat())
            status = entry.get("status", "") if entry else ""
            prefix = "• " if status in {"completed", "partial"} else ("× " if status == "missed" else "")
            text = f"{prefix}{day.day}"
            btn = QPushButton(text)
            btn.setToolTip(
                f"{status or 'No entry'} · {money(entry.get('amount', 0), self.state)}"
                if entry else "No entry"
            )
            if status in {"completed", "partial"}:
                btn.setStyleSheet(f"background: #3a4138; color: {OK};")
            elif status == "missed":
                btn.setStyleSheet(f"color: {RED};")
            btn.clicked.connect(lambda checked=False, d=day: self.open_day(goal, d))
            row, col = (index + offset) // 7 + 1, (index + offset) % 7
            self.calendar_grid.addWidget(btn, row, col)

    def _set_calendar_view(self, view: str, goal: dict[str, Any]) -> None:
        self.calendar_view = view
        self._fill_calendar(goal)

    def _shift_calendar(self, direction: int, goal: dict[str, Any]) -> None:
        if self.calendar_view == "day":
            self.calendar_cursor += timedelta(days=direction)
        elif self.calendar_view == "week":
            self.calendar_cursor += timedelta(days=direction * 7)
        elif self.calendar_view == "month":
            month = self.calendar_cursor.month - 1 + direction
            year = self.calendar_cursor.year + month // 12
            self.calendar_cursor = self.calendar_cursor.replace(year=year, month=month % 12 + 1, day=1)
        else:
            self.calendar_cursor = self.calendar_cursor.replace(year=self.calendar_cursor.year + direction)
        self._fill_calendar(goal)

    def _calendar_today(self, goal: dict[str, Any]) -> None:
        self.calendar_cursor = date.today()
        if self.calendar_view == "month":
            self.calendar_cursor = self.calendar_cursor.replace(day=1)
        self._fill_calendar(goal)

    def _open_calendar_month(self, month: int, goal: dict[str, Any]) -> None:
        self.calendar_cursor = self.calendar_cursor.replace(month=month, day=1)
        self.calendar_view = "month"
        self.render_savings()

    def open_day(self, goal: dict[str, Any], day: date) -> None:
        old = goal.get("entries", {}).get(day.isoformat(), {})
        dialog = EntryDialog(day.strftime("%B %d, %Y"), self)
        dialog.add_amount("amount", "Amount saved", old.get("amount"))
        dialog.add_notes("notes", "Notes", old.get("notes", ""))
        dialog.add_combo("status", "Status", ["completed", "partial", "missed", "skip"], old.get("status", "completed"))
        if old:
            remove = QPushButton("REMOVE ENTRY")
            dialog.form.addRow(remove)
            remove.clicked.connect(lambda: (dialog.done(2)))
        result = dialog.exec()
        if result == 2:
            def remove_entry(state: dict[str, Any]) -> None:
                del next(g for g in state["goals"] if g["id"] == goal["id"])["entries"][day.isoformat()]
                logic.activity(state, f'Removed entry on {day:%b %d} for "{goal["name"]}"', "goal")
            self._change(remove_entry)
            return
        if result != QDialog.DialogCode.Accepted:
            return
        def save_entry(state: dict[str, Any]) -> None:
            item = next(g for g in state["goals"] if g["id"] == goal["id"])
            item.setdefault("entries", {})[day.isoformat()] = {
                "amount": dialog.value("amount"), "notes": dialog.value("notes"),
                "status": dialog.value("status"),
            }
            logic.activity(state, f'Logged {money(dialog.value("amount"), state)} for "{goal["name"]}" on {day:%b %d}', "goal")
        self._change(save_entry)

    def render_budget(self) -> None:
        layout = self.page_layout(2)
        cfg = self.state["budgetConfig"]
        start, end = logic.period_range(self.state)
        remaining = cfg["amount"] - logic.spent_in_range(self.state, start, end)
        totals = logic.category_totals(self.state)
        highest = max(totals.items(), key=lambda item: item[1], default=(None, 0))
        lowest = min(totals.items(), key=lambda item: item[1], default=(None, 0))
        day_totals = logic.daily_totals(self.state)
        highest_day = max(day_totals.items(), key=lambda item: item[1], default=(None, 0))
        self._add_top(layout, "Budget Tracker", f"{cfg['type'].upper()} BUDGET · {money(cfg['amount'], self.state)}", [
            button("CONFIGURE BUDGET", self.open_budget_config),
            button("CATEGORIES", self.manage_categories),
            button("+ ADD EXPENSE", self.open_expense, True),
        ])
        today = date.today()
        week_start = today - timedelta(days=(today.weekday() + 1) % 7)
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)
        self._metric_grid(layout, [
            ("Remaining Budget", money(remaining, self.state), "over budget" if remaining < 0 else "on track"),
            ("Spent Today", money(logic.spent_in_range(self.state, today, today), self.state), ""),
            ("Spent This Week", money(logic.spent_in_range(self.state, week_start, week_start + timedelta(days=6)), self.state), ""),
            ("Spent This Month", money(logic.spent_in_range(self.state, month_start, today), self.state), ""),
            ("Spent This Year", money(logic.spent_in_range(self.state, year_start, today), self.state), ""),
            ("Avg Daily Spending", money(logic.average_daily_spending(self.state), self.state), ""),
            ("Highest Spending Day", money(highest_day[1], self.state) if highest_day[0] else "—", highest_day[0] or ""),
            ("Budget Health Score", str(logic.budget_health(self.state)), "out of 100"),
            ("Highest Category", highest[0] or "—", money(highest[1], self.state) if highest[0] else ""),
            ("Lowest Category", lowest[0] or "—", money(lowest[1], self.state) if lowest[0] else ""),
            ("Projected Period Spend", money(logic.projected_budget(self.state), self.state), ""),
        ])
        monthly = logic.monthly_spend_series(self.state)
        self._chart(layout, "Category Distribution", "donut", list(totals), list(totals.values()))
        self._chart(layout, "Monthly Trend", "line", [x[0] for x in monthly], [x[1] for x in monthly])
        self._chart(layout, "Budget vs Actual (6mo)", "grouped", [x[0] for x in monthly], [cfg["amount"]] * 6, [x[1] for x in monthly])
        filters = QHBoxLayout()
        category = QComboBox()
        category.addItems(["All Categories", *self.state["categories"]])
        category.setCurrentText(self.expense_filters["category"])
        category.currentTextChanged.connect(lambda text: self._filter_expenses("category", text))
        method = QComboBox()
        method.addItems(["All Methods", *logic.PAYMENT_METHODS])
        method.setCurrentText(self.expense_filters["method"])
        method.currentTextChanged.connect(lambda text: self._filter_expenses("method", text))
        from_date = QDateEdit()
        from_date.setCalendarPopup(True)
        from_date.setDisplayFormat("yyyy-MM-dd")
        from_date.setSpecialValueText("From date")
        from_date.setMinimumDate(QDate(1900, 1, 1))
        from_date.setDate(QDate.fromString(self.expense_filters["from"], "yyyy-MM-dd") if self.expense_filters["from"] else from_date.minimumDate())
        from_date.dateChanged.connect(lambda value: self._filter_expenses("from", "" if value == from_date.minimumDate() else value.toString("yyyy-MM-dd")))
        to_date = QDateEdit()
        to_date.setCalendarPopup(True)
        to_date.setDisplayFormat("yyyy-MM-dd")
        to_date.setSpecialValueText("To date")
        to_date.setMinimumDate(QDate(1900, 1, 1))
        to_date.setDate(QDate.fromString(self.expense_filters["to"], "yyyy-MM-dd") if self.expense_filters["to"] else to_date.minimumDate())
        to_date.dateChanged.connect(lambda value: self._filter_expenses("to", "" if value == to_date.minimumDate() else value.toString("yyyy-MM-dd")))
        for widget in (category, method, from_date, to_date):
            filters.addWidget(widget)
        layout.addLayout(filters)
        expenses = list(self.state["expenses"])
        filter_values = self.expense_filters
        if filter_values["category"] != "All Categories":
            expenses = [e for e in expenses if e["category"] == filter_values["category"]]
        if filter_values["method"] != "All Methods":
            expenses = [e for e in expenses if e["method"] == filter_values["method"]]
        if filter_values["from"]:
            expenses = [e for e in expenses if e["date"] >= filter_values["from"]]
        if filter_values["to"]:
            expenses = [e for e in expenses if e["date"] <= filter_values["to"]]
        expenses.sort(key=lambda e: e["date"], reverse=True)
        table = QTableWidget(len(expenses), 6)
        table.setHorizontalHeaderLabels(["Date", "Title", "Category", "Method", "Amount", "Actions"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.horizontalHeader().setStretchLastSection(True)
        for row, expense in enumerate(expenses):
            for col, text in enumerate([
                expense["date"], expense["title"], expense["category"],
                expense["method"], money(expense["amount"], self.state),
            ]):
                table.setItem(row, col, QTableWidgetItem(text))
            controls = QWidget()
            row_actions = QHBoxLayout(controls)
            row_actions.setContentsMargins(2, 0, 2, 0)
            row_actions.addWidget(button("EDIT", lambda item=expense: self.open_expense(item["id"])))
            row_actions.addWidget(button("DEL", lambda item=expense: self.delete_expense(item["id"]), danger=True))
            table.setCellWidget(row, 5, controls)
        table.resizeColumnsToContents()
        table.setMinimumHeight(min(400, max(120, (len(expenses) + 1) * 38)))
        layout.addWidget(table)

    def _filter_expenses(self, key: str, value: str) -> None:
        self.expense_filters[key] = value
        self.render_budget()

    @staticmethod
    def _table(headers: list[str], rows: list[tuple[str, ...]]) -> QTableWidget:
        table = QTableWidget(len(rows), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
        table.resizeColumnsToContents()
        return table

    @staticmethod
    def _activity_date(timestamp: Any) -> str:
        value = float(timestamp or 0)
        if abs(value) >= 100_000_000_000:
            value /= 1000
        try:
            return datetime.fromtimestamp(value).strftime("%b %d")
        except (OverflowError, OSError, ValueError):
            return "—"

    def render_debts(self) -> None:
        layout = self.page_layout(3)
        debts = self.state["debts"]
        owed_to_you = sum(logic.debt_owed(d) for d in debts if d["direction"] != "i-owe")
        you_owe = sum(logic.debt_owed(d) for d in debts if d["direction"] == "i-owe")
        overdue = sum(logic.debt_status(d) == "overdue" for d in debts)
        received = sum(
            logic.debt_paid(d) for d in debts if d["direction"] != "i-owe"
        )
        self._add_top(layout, "Debt Tracker", f"{len(debts)} entr(y/ies) · {overdue} overdue", [
            button("+ NEW ENTRY", self.open_debt, True),
        ])
        self._metric_grid(layout, [
            ("Owed to You", money(owed_to_you, self.state), "Includes money others owe you"),
            ("You Owe", money(you_owe, self.state), "Money you owe others"),
            ("Total Received", money(received, self.state), ""),
        ])
        if not debts:
            layout.addWidget(label("No entries tracked yet. Add money you owe or money someone owes you.", "dim"))
            return
        table = QTableWidget(len(debts), 7)
        table.setHorizontalHeaderLabels([
            "Person / Direction", "Owed", "Interest", "Status", "Paid", "Due", "Actions",
        ])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.horizontalHeader().setStretchLastSection(True)
        for row, debt in enumerate(debts):
            receivable = debt["direction"] != "i-owe"
            status = logic.debt_status(debt)
            table.setItem(row, 0, QTableWidgetItem(
                f"{debt['borrower']} owes you" if receivable else f"You owe {debt['borrower']}"
            ))
            table.setItem(row, 1, QTableWidgetItem(money(logic.debt_owed(debt), self.state)))
            table.setItem(row, 2, QTableWidgetItem(money(logic.debt_interest(debt), self.state)))
            table.setItem(row, 3, QTableWidgetItem(status.upper()))
            table.setItem(row, 4, QTableWidgetItem(money(logic.debt_paid(debt), self.state)))
            table.setItem(row, 5, QTableWidgetItem(debt["dueDate"]))
            controls = QWidget()
            actions = QHBoxLayout(controls)
            actions.setContentsMargins(2, 0, 2, 0)
            actions.addWidget(button("PAY", lambda item=debt: self.open_payment(item["id"])))
            actions.addWidget(button("TIMELINE", lambda item=debt: self.open_timeline(item)))
            actions.addWidget(button("EDIT", lambda item=debt: self.open_debt(item["id"])))
            actions.addWidget(button("DEL", lambda item=debt: self.delete_debt(item["id"]), danger=True))
            table.setCellWidget(row, 6, controls)
        table.setMinimumHeight(min(500, max(140, (len(debts) + 1) * 55)))
        layout.addWidget(table)

    def render_analytics(self) -> None:
        layout = self.page_layout(4)
        values = logic.analytics(self.state)
        self._add_top(layout, "Analytics", "Full financial overview")
        self._metric_grid(layout, [
            ("Money Saved", money(values["saved"], self.state), ""),
            ("Money Spent", money(values["spent"], self.state), ""),
            ("Net Gain / Loss", money(values["net"], self.state), ""),
            ("Net Debt Position", money(values["net_debt"], self.state),
             f"Owed to you {money(values['owed_to_you'], self.state)} · You owe {money(values['you_owe'], self.state)}"),
            ("Savings Rate", f"{values['savings_rate']:.1f}%", ""),
            ("Budget Accuracy", f"{values['budget_accuracy']:.0f}%", ""),
            ("Collection Rate", f"{values['collection_rate']:.0f}%", ""),
            ("Financial Health Score", str(values["health"]), ""),
            ("Avg Weekly Savings", money(values["avg_weekly_savings"], self.state), ""),
            ("Avg Monthly Spending", money(values["avg_monthly_spending"], self.state), ""),
            ("Savings Consistency", f"{values['savings_consistency']:.0f}%", ""),
            ("Longest Saving Streak", f"{values['longest_streak']}d", ""),
            ("Projected Year-End Savings", money(values["year_end_savings"], self.state), ""),
            ("Projected Debt Collection", money(values["projected_collection"], self.state), ""),
            ("Projected Budget (period end)", money(values["projected_budget"], self.state), ""),
        ])
        heat_group = QGroupBox("Contribution Heatmap — Last 6 Months")
        heat_layout = QGridLayout(heat_group)
        heat_layout.setSpacing(3)
        heat = values["heatmap"]
        start = date.today() - timedelta(days=181)
        for index in range(182):
            current = start + timedelta(days=index)
            amount = heat.get(current.isoformat(), 0)
            cell = QLabel(" ")
            cell.setToolTip(f"{current.isoformat()} · {amount} contribution(s)")
            color = "#3a3b39" if amount == 0 else ["#4c5150", "#626d6c", "#798989", DIM][min(3, amount - 1)]
            cell.setStyleSheet(f"background:{color}; border:1px solid {LINE}; min-width:8px; min-height:9px;")
            heat_layout.addWidget(cell, index // 26, index % 26)
        layout.addWidget(heat_group)
        savings_by_month: dict[str, float] = {}
        for goal in self.state["goals"]:
            for entry_date, entry in logic.goal_contributions(goal):
                month = entry_date[:7]
                savings_by_month[month] = savings_by_month.get(month, 0) + entry.get("amount", 0)
        cumulative = 0.0
        labels: list[str] = []
        saved_series: list[float] = []
        for month in sorted(savings_by_month):
            cumulative += savings_by_month[month]
            labels.append(month[2:])
            saved_series.append(cumulative)
        if not labels:
            labels = [date.today().strftime("%y-%m")]
            saved_series = [values["saved"]]
        self._chart(layout, "Savings Growth Trend", "line", labels, saved_series)
        insights_group = QGroupBox("Smart Insights")
        insights_layout = QVBoxLayout(insights_group)
        for insight in values["insights"]:
            insights_layout.addWidget(label("•  " + insight, "dim"))
        layout.addWidget(insights_group)

    def render_settings(self) -> None:
        layout = self.page_layout(5)
        self._add_top(layout, "Settings", "Preferences, data & currency")
        currency_group = QGroupBox("Currency")
        currency_layout = QHBoxLayout(currency_group)
        currency = QComboBox()
        for symbol, code in logic.CURRENCIES:
            currency.addItem(f"{symbol}  {code}", symbol)
        index = currency.findData(self.state["settings"]["currency"])
        if index >= 0:
            currency.setCurrentIndex(index)
        currency.currentIndexChanged.connect(
            lambda: self._update_setting("currency", currency.currentData())
        )
        currency_layout.addWidget(currency)
        currency_layout.addStretch()
        layout.addWidget(currency_group)
        theme_group = QGroupBox("Appearance")
        theme_layout = QHBoxLayout(theme_group)
        theme = QComboBox()
        theme.addItems(["dark", "light", "pureblack", "highcontrast"])
        theme.setCurrentText(self.state["settings"].get("theme", "dark"))
        theme.currentTextChanged.connect(lambda value: self._update_setting("theme", value))
        theme_layout.addWidget(theme)
        theme_layout.addStretch()
        layout.addWidget(theme_group)
        data_group = QGroupBox("Data")
        data_layout = QHBoxLayout(data_group)
        data_layout.addWidget(button("EXPORT DATA", self.export_data))
        data_layout.addWidget(button("IMPORT DATA", self.import_data))
        data_layout.addWidget(button("RESET ALL DATA", self.reset_data, danger=True))
        data_layout.addStretch()
        layout.addWidget(data_group)
        path_label = label(f"Database location: {self.storage.path}", "faint")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(path_label)

    def _update_setting(self, key: str, value: str) -> None:
        if self.state["settings"].get(key) == value:
            return
        candidate = copy.deepcopy(self.state)
        candidate["settings"][key] = value
        if self._save_state(candidate):
            if key == "theme":
                self.setStyleSheet(self._style_for_theme(value))

    @staticmethod
    def _style_for_theme(theme: str) -> str:
        if theme == "dark":
            return BudgetWindow._style()
        if theme == "light":
            return BudgetWindow._style().replace(
                BG, "#f0f1f2"
            ).replace(RAISED, "#e5e5e2").replace(CARD, "#e5e5e2").replace(
                LINE, "#888c79"
            ).replace(FG, "#262626").replace(DIM, "#3a3b39").replace(FAINT, "#595959")
        if theme == "pureblack":
            return BudgetWindow._style().replace(BG, "#000000").replace(
                RAISED, "#080808"
            ).replace(CARD, "#080808").replace(LINE, "#595959")
        return BudgetWindow._style().replace(BG, "#000000").replace(
            RAISED, "#000000"
        ).replace(CARD, "#000000").replace(LINE, "#f0f1f2").replace(
            FG, "#ffffff"
        ).replace(DIM, "#f0f1f2").replace(FAINT, "#ffffff")

    def search_changed(self, query: str) -> None:
        self._clear_layout(self.search_results_layout)
        query = query.strip().casefold()
        self.search_results.setVisible(bool(query))
        if not query:
            return
        results: list[tuple[str, int, str | None]] = []
        for goal in self.state["goals"]:
            if query in goal["name"].casefold():
                results.append((goal["name"], 1, goal["id"]))
        for expense in self.state["expenses"]:
            if any(query in str(expense.get(key, "")).casefold() for key in ("title", "category", "notes")):
                results.append((f'{expense["title"]} — {money(expense["amount"], self.state)}', 2, None))
        for debt in self.state["debts"]:
            if query in debt["borrower"].casefold() or query in str(debt.get("notes", "")).casefold():
                results.append((f'{debt["borrower"]} — {money(debt["amount"], self.state)}', 3, None))
        for category in self.state["categories"]:
            if query in category.casefold():
                results.append((category, 2, None))
        if not results:
            self.search_results_layout.addWidget(label("NO MATCHES FOUND", "faint"))
            return
        for text, tab_index, goal_id in results[:20]:
            item = button(text, lambda i=tab_index, gid=goal_id: self._open_search_result(i, gid))
            self.search_results_layout.addWidget(item)

    def _open_search_result(self, tab_index: int, goal_id: str | None) -> None:
        if goal_id:
            self.current_goal_id = goal_id
        self.tabs.setCurrentIndex(tab_index)
        self.search.clear()
        self.search_results.hide()

    def _dialog(self, dialog: EntryDialog, save: Callable[[EntryDialog], None]) -> None:
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                save(dialog)
            except ValueError as error:
                QMessageBox.warning(self, "Check your entry", str(error))

    def open_expense(self, expense_id: str | None = None) -> None:
        old = next((e for e in self.state["expenses"] if e["id"] == expense_id), None)
        dialog = EntryDialog("Edit Expense" if old else "Add Expense", self)
        dialog.add_text("title", "Title", old.get("title", "") if old else "", "Groceries")
        dialog.add_amount("amount", "Amount", old.get("amount") if old else None, 0)
        dialog.add_date("date", "Date", old.get("date") if old else None)
        dialog.add_combo(
            "category", "Category", self.state["categories"],
            old.get("category") if old else self.state["categories"][0],
        )
        dialog.add_combo("method", "Payment Method", logic.PAYMENT_METHODS, old.get("method") if old else "Cash")
        dialog.add_notes("notes", "Notes", old.get("notes", "") if old else "")

        def save(form: EntryDialog) -> None:
            if not form.value("title"):
                raise ValueError("Expense title is required.")
            if form.value("amount") <= 0:
                raise ValueError("Expense amount must be greater than zero.")
            def operation(state: dict[str, Any]) -> None:
                item = next((e for e in state["expenses"] if e["id"] == expense_id), None) if old else None
                if item is None:
                    item = {"id": logic.new_id()}
                    state["expenses"].append(item)
                item.update({key: form.value(key) for key in ("title", "amount", "date", "category", "method", "notes")})
                logic.activity(state, f'Logged {money(item["amount"], state)} — {item["title"]}' if not old else f'Updated expense "{item["title"]}"', "expense")
            self._change(operation)
        self._dialog(dialog, save)

    def delete_expense(self, expense_id: str) -> None:
        old = next(e for e in self.state["expenses"] if e["id"] == expense_id)
        if QMessageBox.question(self, "Delete expense", f'Delete expense "{old["title"]}"?') != QMessageBox.StandardButton.Yes:
            return
        def operation(state: dict[str, Any]) -> None:
            item = next(e for e in state["expenses"] if e["id"] == expense_id)
            state["deleted"].append({"type": "expense", "data": item, "ts": datetime.now().timestamp()})
            state["expenses"] = [e for e in state["expenses"] if e["id"] != expense_id]
            logic.activity(state, f'Deleted expense "{old["title"]}"', "expense")
        if self._change(operation):
            self._show_undo("expense", old)

    def open_goal(self, goal_id: str | None = None) -> None:
        old = next((g for g in self.state["goals"] if g["id"] == goal_id), None)
        dialog = EntryDialog("Edit Savings Goal" if old else "New Savings Goal", self)
        dialog.add_text("name", "Goal Name", old.get("name", "") if old else "", "Emergency fund")
        dialog.add_amount("target", "Target Amount", old.get("target") if old else None)
        dialog.add_date("startDate", "Start Date", old.get("startDate") if old else None)
        dialog.add_date("targetDate", "Target Date", old.get("targetDate") if old else None, allow_empty=True)
        method = dialog.add_combo(
            "method", "Saving Method", ["daily", "weekly", "biweekly", "monthly", "custom"],
            old.get("method") if old else "weekly",
        )
        custom = dialog.add_int("customDays", "Custom interval (days)", old.get("customDays", 7) if old else 7)
        custom.setEnabled(method.currentText() == "custom")
        method.currentTextChanged.connect(lambda value: custom.setEnabled(value == "custom"))

        def save(form: EntryDialog) -> None:
            if not form.value("name"):
                raise ValueError("Goal name is required.")
            if form.value("target") <= 0:
                raise ValueError("Goal target must be greater than zero.")
            if form.value("targetDate") < form.value("startDate"):
                raise ValueError("Target date must be on or after the start date.")
            def operation(state: dict[str, Any]) -> None:
                item = next((g for g in state["goals"] if g["id"] == goal_id), None) if old else None
                if item is None:
                    item = {"id": logic.new_id(), "entries": {}, "createdAt": datetime.now().timestamp()}
                    state["goals"].append(item)
                item.update({key: form.value(key) for key in ("name", "target", "startDate", "targetDate", "method", "customDays")})
                logic.activity(state, f'Updated goal "{item["name"]}"' if old else f'Created goal "{item["name"]}" ({money(item["target"], state)})', "goal")
                if not old:
                    self.current_goal_id = item["id"]
            self._change(operation)
        self._dialog(dialog, save)

    def delete_goal(self, goal_id: str) -> None:
        old = next(g for g in self.state["goals"] if g["id"] == goal_id)
        answer = QMessageBox.question(
            self, "Delete savings goal",
            f'Delete "{old["name"]}"? This removes all contribution history for this goal.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        def operation(state: dict[str, Any]) -> None:
            item = next(g for g in state["goals"] if g["id"] == goal_id)
            state["deleted"].append({"type": "goal", "data": item, "ts": datetime.now().timestamp()})
            state["goals"] = [g for g in state["goals"] if g["id"] != goal_id]
            state["activity"].insert(0, {"id": logic.new_id(), "text": f'Deleted goal "{old["name"]}"', "type": "goal", "ts": datetime.now().timestamp()})
            self.current_goal_id = None
        if self._change(operation):
            self._show_undo("goal", old)

    def open_quick_contribution(self) -> None:
        if not self.state["goals"]:
            QMessageBox.information(self, "Savings goal required", "Create a savings goal first.")
            return
        names = {g["name"]: g["id"] for g in self.state["goals"]}
        dialog = EntryDialog("Quick Contribution", self)
        dialog.add_combo("goal", "Goal", list(names))
        dialog.add_amount("amount", "Amount")
        def save(form: EntryDialog) -> None:
            if form.value("amount") <= 0:
                raise ValueError("Enter an amount greater than zero.")
            goal_id = names[form.value("goal")]
            def operation(state: dict[str, Any]) -> None:
                goal = next(g for g in state["goals"] if g["id"] == goal_id)
                today_text = date.today().isoformat()
                old = goal.setdefault("entries", {}).get(today_text, {})
                goal["entries"][today_text] = {
                    "amount": old.get("amount", 0) + form.value("amount"),
                    "notes": old.get("notes", ""), "status": "completed",
                }
                logic.activity(state, f'Contributed {money(form.value("amount"), state)} to "{goal["name"]}"', "goal")
            self._change(operation)
        self._dialog(dialog, save)

    def open_budget_config(self) -> None:
        old = self.state["budgetConfig"]
        dialog = EntryDialog("Configure Budget", self)
        kind = dialog.add_combo("type", "Budget Type", ["weekly", "monthly", "yearly", "custom"], old["type"])
        dialog.add_amount("amount", "Budget Amount", old["amount"])
        start = dialog.add_date("customStart", "Custom Start", old.get("customStart"), allow_empty=True)
        end = dialog.add_date("customEnd", "Custom End", old.get("customEnd"), allow_empty=True)
        start.setEnabled(kind.currentText() == "custom")
        end.setEnabled(kind.currentText() == "custom")
        kind.currentTextChanged.connect(lambda value: (start.setEnabled(value == "custom"), end.setEnabled(value == "custom")))
        def save(form: EntryDialog) -> None:
            if kind.currentText() == "custom" and form.value("customStart") > form.value("customEnd"):
                raise ValueError("Custom budget start must be on or before its end.")
            def operation(state: dict[str, Any]) -> None:
                state["budgetConfig"] = {
                    "type": form.value("type"), "amount": form.value("amount"),
                    "customStart": form.value("customStart"), "customEnd": form.value("customEnd"),
                }
                logic.activity(state, f'Set {form.value("type")} budget to {money(form.value("amount"), state)}', "budget")
            self._change(operation)
        self._dialog(dialog, save)

    def manage_categories(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Manage Categories")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)
        table = QTableWidget(len(self.state["categories"]), 2)
        table.setHorizontalHeaderLabels(["Category", ""])
        table.horizontalHeader().setStretchLastSection(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, category in enumerate(self.state["categories"]):
            table.setItem(row, 0, QTableWidgetItem(category))
            table.setCellWidget(row, 1, button(
                "REMOVE", lambda value=category: self._remove_category(value, dialog), danger=True,
            ))
        layout.addWidget(table)
        row = QHBoxLayout()
        new_category = QLineEdit()
        new_category.setPlaceholderText("e.g. Pets")
        add = button("ADD", lambda: self._add_category(new_category, dialog), True)
        row.addWidget(new_category)
        row.addWidget(add)
        layout.addLayout(row)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(dialog.reject)
        close.accepted.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def _add_category(self, field: QLineEdit, dialog: QDialog) -> None:
        value = field.text().strip()
        if not value:
            QMessageBox.warning(dialog, "Category required", "Enter a category name.")
            return
        if value in self.state["categories"]:
            QMessageBox.warning(dialog, "Already exists", "That category already exists.")
            return
        candidate = copy.deepcopy(self.state)
        candidate["categories"].append(value)
        if self._save_state(candidate):
            dialog.accept()
            self.manage_categories()

    def _remove_category(self, category: str, dialog: QDialog) -> None:
        if len(self.state["categories"]) <= 1:
            QMessageBox.warning(dialog, "Category required", "At least one expense category must remain.")
            return
        candidate = copy.deepcopy(self.state)
        candidate["categories"].remove(category)
        if self._save_state(candidate):
            dialog.accept()
            self.manage_categories()

    def open_debt(self, debt_id: str | None = None) -> None:
        old = next((d for d in self.state["debts"] if d["id"] == debt_id), None)
        dialog = EntryDialog("Edit Debt Entry" if old else "New Debt Entry", self)
        dialog.add_combo("direction", "Who owes whom?", ["owed-to-me", "i-owe"], old.get("direction") if old else "owed-to-me")
        dialog.add_text("borrower", "Other Person", old.get("borrower", "") if old else "")
        dialog.add_amount("amount", "Starting Amount", old.get("amount") if old else None)
        dialog.add_date("dateBorrowed", "Start Date", old.get("dateBorrowed") if old else None)
        dialog.add_amount("rate", "Interest Rate (%)", old.get("rate", 0) if old else 0)
        dialog.add_date("dueDate", "Payment Due Date", old.get("dueDate") if old else None, allow_empty=True)
        dialog.add_combo("interestType", "Interest Type", ["none", "simple", "compound"], old.get("interestType") if old else "none")
        dialog.add_combo("interestFreq", "Interest Frequency", ["daily", "weekly", "monthly", "yearly"], old.get("interestFreq") if old else "monthly")
        dialog.add_text("phone", "Phone Number", old.get("phone", "") if old else "")
        dialog.add_combo("status", "Status", ["active", "paid", "overdue"], old.get("status") if old else "active")
        dialog.add_notes("notes", "Notes", old.get("notes", "") if old else "")
        def save(form: EntryDialog) -> None:
            if not form.value("borrower"):
                raise ValueError("Other person is required.")
            if form.value("amount") <= 0:
                raise ValueError("Starting amount must be greater than zero.")
            def operation(state: dict[str, Any]) -> None:
                item = next((d for d in state["debts"] if d["id"] == debt_id), None) if old else None
                if item is None:
                    item = {"id": logic.new_id(), "payments": []}
                    state["debts"].append(item)
                item.update({key: form.value(key) for key in (
                    "direction", "borrower", "amount", "dateBorrowed", "rate", "dueDate",
                    "interestType", "interestFreq", "phone", "status", "notes",
                )})
                text = f'Updated debt entry for {item["borrower"]}' if old else (
                    f'Added debt owed to {item["borrower"]}' if item["direction"] == "i-owe"
                    else f'Added debt owed by {item["borrower"]}'
                )
                logic.activity(state, text, "debt")
            self._change(operation)
        self._dialog(dialog, save)

    def open_payment(self, debt_id: str) -> None:
        debt = next(d for d in self.state["debts"] if d["id"] == debt_id)
        receivable = debt["direction"] != "i-owe"
        dialog = EntryDialog("Record Payment", self)
        dialog.add_amount("amount", "Amount")
        dialog.add_date("date", "Date")
        dialog.add_notes("notes", "Notes")
        def save(form: EntryDialog) -> None:
            if form.value("amount") <= 0:
                raise ValueError("Enter an amount greater than zero.")
            def operation(state: dict[str, Any]) -> None:
                item = next(d for d in state["debts"] if d["id"] == debt_id)
                item.setdefault("payments", []).append({
                    "id": logic.new_id(), "amount": form.value("amount"),
                    "date": form.value("date"), "notes": form.value("notes"),
                })
                if logic.debt_owed(item) <= 0.5:
                    item["status"] = "paid"
                action = "Received payment from" if receivable else "Paid"
                logic.activity(state, f'{action} {debt["borrower"]}: {money(form.value("amount"), state)}', "debt")
            self._change(operation)
        self._dialog(dialog, save)

    def open_timeline(self, debt: dict[str, Any]) -> None:
        events = [(debt["dateBorrowed"], f'{ "Lent" if debt["direction"] != "i-owe" else "Borrowed" } {money(debt["amount"], self.state)}')]
        for payment in debt.get("payments", []):
            action = "Received" if debt["direction"] != "i-owe" else "Paid"
            note = f' — {payment["notes"]}' if payment.get("notes") else ""
            events.append((payment["date"], f'{action} {money(payment["amount"], self.state)}{note}'))
        events.append((debt["dueDate"], "Due date"))
        events.sort(key=lambda item: item[0])
        dialog = QDialog(self)
        dialog.setWindowTitle(f'Timeline — {debt["borrower"]}')
        box = QVBoxLayout(dialog)
        for event_date, text in events:
            box.addWidget(label(f"{event_date}   {text}", "dim"))
        close = button("CLOSE", dialog.accept)
        box.addWidget(close)
        dialog.exec()

    def delete_debt(self, debt_id: str) -> None:
        debt = next(d for d in self.state["debts"] if d["id"] == debt_id)
        if QMessageBox.question(self, "Delete debt", f'Delete debt entry for "{debt["borrower"]}"?') != QMessageBox.StandardButton.Yes:
            return
        def operation(state: dict[str, Any]) -> None:
            item = next(d for d in state["debts"] if d["id"] == debt_id)
            state["deleted"].append({"type": "debt", "data": item, "ts": datetime.now().timestamp()})
            state["debts"] = [d for d in state["debts"] if d["id"] != debt_id]
            logic.activity(state, f'Deleted debt entry for {debt["borrower"]}', "debt")
        if self._change(operation):
            self._show_undo("debt", debt)

    def export_data(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Budget Tracker Data",
            str(Path.home() / f"budget-tracker-export-{date.today().isoformat()}.json"),
            "JSON files (*.json)",
        )
        if not path:
            return
        try:
            self.storage.write_json(path, self.state)
        except StorageError as error:
            QMessageBox.critical(self, "Export failed", str(error))
            return
        QMessageBox.information(self, "Export complete", "Data exported successfully.")

    def import_data(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Budget Tracker Data", "", "JSON files (*.json)")
        if not path:
            return
        try:
            imported = self.storage.read_json(path)
        except StorageError as error:
            QMessageBox.critical(self, "Import failed", str(error))
            return
        answer = QMessageBox.question(
            self, "Replace local data?",
            "Importing replaces all current goals, expenses, debts, categories and settings. "
            "Export a backup first if you may need the current data. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._save_state(imported)

    def reset_data(self) -> None:
        answer = QMessageBox.question(
            self, "Reset all data",
            "This permanently erases all goals, expenses and debt records. This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._save_state(logic.defaults())
