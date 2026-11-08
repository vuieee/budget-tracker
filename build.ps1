$ErrorActionPreference = "Stop"

python -m PyInstaller --noconfirm --clean BudgetTracker.spec

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

Write-Host "Executable created at dist\BudgetTracker.exe"
