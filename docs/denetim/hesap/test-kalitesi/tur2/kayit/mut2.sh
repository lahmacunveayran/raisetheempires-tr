#!/bin/sh
# the audit's surviving save mutants, again, against this worktree's tests
K=<S>/fix2/kayit
D=<S>/denetim2
cd "<HOME>/Desktop/Raise/raisetheempires-pr/.claude/worktrees/agent-a60a9e23f98052837" || exit 9
WT="$(pwd -W)"
TESTS="test/save_backup_test.py test/save_migration_test.py test/save_server_test.py test/session_layer_test.py test/empires_test.py test/save_actions_test.py test/state_machine_test.py"
for name in server_save; do
  PYTHONUTF8=1 PYTHONIOENCODING=utf-8 "<HOME>/Desktop/Raise/venv312/Scripts/python.exe" "$K/remut.py" --wt "$WT" --json "$D/mut_$name.json" --out "$K/remut_$name.json" --timeout 200 $TESTS
done
echo ALL DONE
