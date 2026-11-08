# Budget Tracker Desktop

<<<<<<< HEAD
A native Windows desktop budget, savings, and debt tracker built with Python and PySide6. The app is local-first and does not need a network connection.

## Run from source

1. Install Python 3.10 or later.
2. In PowerShell, from this project directory, run:

   ```powershell
   python -m pip install -r requirements.txt
   python main.py
   ```

## Build the Windows executable

```powershell
python -m pip install -r requirements.txt
.\build.ps1
```

The one-file executable is created at `dist\BudgetTracker.exe`. The executable keeps user data outside its installation folder.

## Data, backup, and browser migration

Application data is kept in SQLite under the current Windows user's Qt application-data directory (normally `%APPDATA%\Budget Tracker\Budget Tracker\budget-tracker.sqlite3`). The app validates records before saving and reports database errors without replacing unreadable data.

Use **Settings → Export Data** to create a JSON backup, **Import Data** to restore a backup, and **Reset All Data** to clear the application. Import and reset both require confirmation. Importing replaces local records, so export a backup first if needed.

To migrate data from the former browser app, open its `index.html`, use **Settings → Export Data** there, then use **Import Data** in the desktop app. The JSON structure and existing records are retained.

## Features

- Dashboard with savings, budget, debt, weekly spending, activity, and quick actions.
- Savings goals, contribution history, daily/weekly/monthly/yearly calendar, streaks, projections, and quick contributions.
- Expense tracking with configurable weekly/monthly/yearly/custom budgets, editable categories, payment methods, date/category/method filters, undoable deletion, and spending charts.
- Debt tracking with direction, simple/compound interest, payment records, timelines, overdue status, and undoable deletion.
- Financial analytics, savings heatmap, growth trend, and spending insights.
- Search, keyboard navigation, currency settings, dark/light/high-contrast themes, JSON import/export, and persistent local storage.

The former browser implementation remains in the repository to support browser-data migration. The desktop app uses only PySide6 and the Python standard library at runtime; charts are drawn with Qt.

## Tests

```powershell
python -m unittest discover -s tests -v
```
=======
Open `index.html` in a browser or publish this folder with GitHub Pages. Data is stored in the browser. Charts load Chart.js from a CDN.
>>>>>>> 90071815f1427c5882123cae7b98e01dfa7a1d70
