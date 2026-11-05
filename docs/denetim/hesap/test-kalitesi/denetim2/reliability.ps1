# Reliability runs (denetim2). Runs in the worktree only.
$sp = Split-Path -Parent $MyInvocation.MyCommand.Path
$wt = Join-Path $sp "wt"
$pytest = "C:\Users\<user>\Desktop\Raise\venv312\Scripts\pytest.exe"
$out = Join-Path $sp "reliability.txt"
Set-Location $wt
$env:PYTHONPATH = "$wt;$sp\plugins"
"reliability runs " + (Get-Date) | Set-Content -Encoding utf8 $out
function Run($label, $extra) {
    $t = Get-Date
    $res = & $pytest -q -p no:cacheprovider -p denetim2_shuffle -p denetim2_leaks @extra test 2>&1 | Select-String -Pattern "passed|failed|error" | Select-Object -Last 1
    "{0,-22} {1}  ({2:N0} s)" -f $label, $res, ((Get-Date)-$t).TotalSeconds | Add-Content -Encoding utf8 $out
}
foreach ($i in 1..3) { $env:SHUFFLE_SEED = ""; $env:DENETIM2_REPORT = Join-Path $sp "leaks_normal$i.txt"; Run "normal order #$i" @() }
$env:SHUFFLE_SEED = "reverse"; $env:DENETIM2_REPORT = Join-Path $sp "leaks_reverse.txt"; Run "reverse order" @()
foreach ($s in 11, 22, 33, 44, 55) { $env:SHUFFLE_SEED = "$s"; $env:DENETIM2_REPORT = Join-Path $sp "leaks_shuffle$s.txt"; Run "shuffled seed $s" @() }
$env:SHUFFLE_SEED = ""
foreach ($f in Get-ChildItem test\*_test.py) {
    $env:DENETIM2_REPORT = Join-Path $sp ("leaks_alone_" + $f.BaseName + ".txt")
    $t = Get-Date
    $res = & $pytest -q -p no:cacheprovider -p denetim2_leaks ("test/" + $f.Name) 2>&1 | Select-String -Pattern "passed|failed|error" | Select-Object -Last 1
    "{0,-34} {1}  ({2:N0} s)" -f ("alone " + $f.Name), $res, ((Get-Date)-$t).TotalSeconds | Add-Content -Encoding utf8 $out
}
