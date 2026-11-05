#!/bin/sh
# run pytest with the kayit launcher from the worktree root
cd "<HOME>/Desktop/Raise/raisetheempires-pr/.claude/worktrees/agent-a60a9e23f98052837" || exit 9
PYTHONPATH="$(pwd -W)" PYTHONUTF8=1 PYTHONIOENCODING=utf-8 "<HOME>/Desktop/Raise/venv312/Scripts/python.exe" "<S>/fix2/kayit/run_pytest_kayit.py" -q -p no:cacheprovider "$@"
