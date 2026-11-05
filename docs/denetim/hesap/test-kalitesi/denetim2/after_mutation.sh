#!/bin/bash
# denetim2: runs after mutation_runs.ps1 (same worktree, so strictly one after the other):
# the 24 targeted mutants, then the whole-suite recheck of every survivor.
D="$(cd "$(dirname "$0")" && pwd)"
PY="<HOME>/Desktop/Raise/venv312/Scripts/python.exe"
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
until [ -f "$D/mut_done.txt" ]; do sleep 20; done
WT="$(cygpath -w "$D/wt")"
"$PY" "$D/targeted_mutants.py" --wt "$WT" > "$D/targeted_mutants.log" 2>&1
"$PY" "$D/mut_recheck.py" --wt "$WT" --json mut_battle_engine.json --json mut_save_engine.json \
    --json mut_server_save.json --json mut_save_migration.json > "$D/mut_recheck.log" 2>&1
echo done > "$D/after_done.txt"
