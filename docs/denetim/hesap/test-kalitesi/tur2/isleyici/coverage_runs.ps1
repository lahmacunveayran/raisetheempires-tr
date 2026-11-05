$PY = "C:\Users\<user>\Desktop\Raise\venv312\Scripts\python.exe"
$I = "<HOME>\AppData\Local\Temp\claude\44db76dc85e0ce87\6e027af0-22bc-435d-8563-59919183e99e\scratchpad\fix2\isleyici"
$env:PYTHONPATH = (Get-Location).Path; $env:PYTHONUTF8 = 1; $env:PYTHONIOENCODING = "utf-8"
foreach ($run in @(@("without", "--ignore=test/server_handlers_test.py"), @("with", "--co-placeholder"))) {
    $name = $run[0]
    $extra = @()
    if ($run[1] -ne "--co-placeholder") { $extra = @($run[1]) }
    & $PY -m coverage run --branch --data-file="$I\cov_$name.data" "$I\run_pytest_isleyici.py" -q -p no:cacheprovider test @extra 2>&1 | Select-Object -Last 3 | Out-File -Encoding utf8 "$I\cov_$name.txt"
    & $PY -m coverage json --data-file="$I\cov_$name.data" -o "$I\cov_$name.json" 2>&1 | Out-Null
    & $PY "$I\uncovered.py" "$I\cov_$name.json" | Out-File -Encoding utf8 -Append "$I\cov_$name.txt"
}
