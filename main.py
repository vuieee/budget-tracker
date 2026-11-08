from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QIcon

from app.storage import BudgetStorage, StorageError
from app.ui import BudgetWindow


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("Budget Tracker")
    application.setOrganizationName("Budget Tracker")
    data_directory = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    try:
        storage = BudgetStorage(Path(data_directory) / "budget-tracker.sqlite3")
        window = BudgetWindow(storage)
        window.setWindowIcon(QIcon(str(resource_path("touch-icon.png"))))
    except (StorageError, OSError) as error:
        QMessageBox.critical(None, "Budget Tracker could not start", str(error))
        return 1
    window.show()
    return application.exec()


def resource_path(name: str) -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return bundle_root / name


if __name__ == "__main__":
    raise SystemExit(main())
