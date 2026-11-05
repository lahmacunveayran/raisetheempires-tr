#!/bin/sh
# runs pytest with the sunucu launcher from the worktree root: rt.sh [pytest args]
W="<HOME>/Desktop/Raise/raisetheempires-pr/.claude/worktrees/agent-a56ad9a6a592f23b3"
S="<S>"
PY="<HOME>/Desktop/Raise/venv312/Scripts/python.exe"
cd "$W" || exit 9
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
export PYTHONPATH="$(pwd -W);$(cd "$S/denetim2/plugins" && pwd -W)"
exec "$PY" "$S/fix2/sunucu/run_pytest_sunucu.py" -q -p no:cacheprovider "$@"
