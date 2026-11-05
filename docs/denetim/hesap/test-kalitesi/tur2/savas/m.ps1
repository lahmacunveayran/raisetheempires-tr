param([string]$cmd, [string]$a, [string]$b = "")
$env:PYTHONIOENCODING = "utf-8"
$py = Join-Path $env:USERPROFILE "Desktop\Raise\venv312\Scripts\python.exe"
Set-Location (Join-Path $env:USERPROFILE "Desktop\Raise\raisetheempires-pr\.claude\worktrees\agent-a3fc98741cb7d98c8")
if ($cmd -eq "method") { & $py turkce\araclar\abc.py assets\ZGame.109338.swf method $a $b 2>&1 }
else { & $py turkce\araclar\abc.py assets\ZGame.109338.swf $cmd $a 2>&1 }
