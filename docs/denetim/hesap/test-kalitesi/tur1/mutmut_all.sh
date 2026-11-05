#!/bin/bash
S="<S>"
PY="<HOME>/Desktop/Raise/venv312/Scripts/python.exe"
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1
cd "$S/mm"
date
"$PY" -m mutmut run --paths-to-mutate "battle_engine.py,bot_empires.py,titan_lab.py" --use-patch-file fix.patch --no-progress \
  --runner "\"$PY\" -m pytest -x -q -p no:cacheprovider test/battle_turn_test.py test/battle_test.py test/titan_lab_test.py test/bot_empires_test.py" > "$S/mutmut_A.log" 2>&1
"$PY" -m mutmut results > "$S/mutmut_A_results.txt" 2>&1
date
cd "$S/mm2"
"$PY" -m mutmut run --paths-to-mutate "empires-server.py,save_engine.py,save_migration.py,state_machine.py,logger.py,game_settings.py" --use-patch-file fix.patch --no-progress \
  --runner "\"$PY\" -m pytest -x -q -p no:cacheprovider test/session_layer_test.py test/empires_test.py test/state_machine_test.py test/save_actions_test.py" > "$S/mutmut_B.log" 2>&1
"$PY" -m mutmut results > "$S/mutmut_B_results.txt" 2>&1
date
