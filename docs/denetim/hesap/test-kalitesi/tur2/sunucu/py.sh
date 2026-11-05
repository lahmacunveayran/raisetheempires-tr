#!/bin/sh
# runs the venv python from the worktree root: py.sh [args]
W="<HOME>/Desktop/Raise/raisetheempires-pr/.claude/worktrees/agent-a56ad9a6a592f23b3"
cd "$W" || exit 9
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
export PYTHONPATH="$(pwd -W)"
exec "<HOME>/Desktop/Raise/venv312/Scripts/python.exe" "$@"
