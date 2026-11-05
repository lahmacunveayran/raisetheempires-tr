$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$py = Join-Path $env:USERPROFILE "Desktop\Raise\venv312\Scripts\python.exe"
$wt = Join-Path $env:USERPROFILE "Desktop\Raise\raisetheempires-pr\.claude\worktrees\agent-a3fc98741cb7d98c8"
$env:PYTHONPATH = $wt
Set-Location $wt
& $py "<HOME>\AppData\Local\Temp\claude\44db76dc85e0ce87\6e027af0-22bc-435d-8563-59919183e99e\scratchpad\fix2\savas\run_pytest_savas.py" -q -p no:cacheprovider @args 2>&1
