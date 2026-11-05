# Mutation runs (denetim2): mutmut 2.5.1 operators through mut_harness.py, in the worktree only. Re-runnable and
# resumable (results already in the JSON files are kept).
$sp = Split-Path -Parent $MyInvocation.MyCommand.Path
$wt = Join-Path $sp "wt"
$py = "C:\Users\<user>\Desktop\Raise\venv312\Scripts\python.exe"
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
$battleTests = @("test/battle_turn_test.py", "test/battle_test.py", "test/titan_lab_test.py", "test/bot_empires_test.py",
    "test/empires_test.py", "test/bounty_center_test.py")
$saveTests = @("test/session_layer_test.py", "test/empires_test.py", "test/save_actions_test.py", "test/state_machine_test.py")
& $py "$sp\mut_harness.py" --wt $wt --file battle_engine.py --covered-only --sample 200 --seed 1 --out "$sp\mut_battle_engine.json" --deselect "test/bot_empires_test.py::test_the_easy_bots_are_beaten_more_often" --deselect "test/bot_empires_test.py::test_bot_units_have_their_animations" --tests @battleTests *> "$sp\mut_battle_engine.log"
& $py "$sp\mut_harness.py" --wt $wt --file save_engine.py --covered-only --seed 1 --out "$sp\mut_save_engine.json" --tests @saveTests *> "$sp\mut_save_engine.log"
& $py "$sp\mut_harness.py" --wt $wt --file empires-server.py --covered-only --sample 150 --seed 1 --ranges "100-213,301-308,523-604,896-1003,3205-3264" --out "$sp\mut_server_save.json" --tests @saveTests *> "$sp\mut_server_save.log"
& $py "$sp\mut_harness.py" --wt $wt --file save_migration.py --covered-only --sample 60 --seed 1 --out "$sp\mut_save_migration.json" --tests "test/session_layer_test.py" "test/empires_test.py" *> "$sp\mut_save_migration.log"
"done" | Set-Content "$sp\mut_done.txt"

