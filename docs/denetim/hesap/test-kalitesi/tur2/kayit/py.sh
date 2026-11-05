#!/bin/sh
# python of the venv, from the worktree root, with the worktree on the path
cd "<HOME>/Desktop/Raise/raisetheempires-pr/.claude/worktrees/agent-a60a9e23f98052837" || exit 9
PYTHONPATH="$(pwd -W)" PYTHONUTF8=1 PYTHONIOENCODING=utf-8 "<HOME>/Desktop/Raise/venv312/Scripts/python.exe" "$@"
