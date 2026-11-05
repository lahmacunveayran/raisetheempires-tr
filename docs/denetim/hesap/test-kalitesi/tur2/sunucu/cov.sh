#!/bin/sh
# branch coverage of the whole suite, data and json kept in the scratch folder
W="<HOME>/Desktop/Raise/raisetheempires-pr/.claude/worktrees/agent-a56ad9a6a592f23b3"
R=<S>/fix2/sunucu
PY="<HOME>/Desktop/Raise/venv312/Scripts/python.exe"
cd "$W" || exit 9
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONPATH="$(pwd -W)" COVERAGE_FILE="$(cd $R && pwd -W)/.coverage"
"$PY" -m coverage run --branch --source="$(pwd -W)" "$R/run_pytest_sunucu.py" -q -p no:cacheprovider -p no:warnings test | tail -2
"$PY" -m coverage json -o "$R/coverage.json" >/dev/null
"$PY" -c "
import json,sys
d=json.load(open(sys.argv[1]))
for k,v in d['files'].items():
    if k.endswith('empires-server.py'):
        s=v['summary']; print(k, 'lines', s['covered_lines'], '/', s['num_statements'], 'branches', s['covered_branches'], '/', s['num_branches'], round(100*s['covered_branches']/s['num_branches'],1), '%')
" "$R/coverage.json"
