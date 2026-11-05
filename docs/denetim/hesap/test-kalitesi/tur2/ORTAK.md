# Common rules for the three fix agents (test-quality round 2)

Project: Raise the Empires private server (Python 3.12, Flask, AMF gateway) plus the original Flash client.
You work in your own git worktree (created for you, branched from commit cb00c06 of branch `denetim-1`).
Other agents work in parallel in other worktrees on OTHER files. Touch only the files your brief lists.
If you need a change in a file you do not own, do not make it: write it in your report.

## Goal
An independent professional audit (read it: `<S>\denetim2\rapor.md`, Turkish) scored the test suite 6/10:
the tests are honest but narrow, some expected values are snapshots / constants without derivation /
circular, some orderings break. Your job: close the gaps of your brief with tests that would catch real faults.

## What a good test is here (non-negotiable)
- The expected value must come from an independent oracle, never from running the code under test:
  - the Flash client's bytecode (the real game's rules), via
    `"<PY>" turkce\araclar\abc.py assets\ZGame.109338.swf method <Class> <method>` and `... refs <regex>`
    (run from your worktree root; decompiled extracts already exist in `<S>\abc\` and `<S>\denetim2\bytecode\`);
  - the game XML `assets\29oct2012\gameSettings_with_fixes.xml` read with ElementTree (see `test\client_settings.py`,
    extend it if you own it, otherwise write your own small reader in your test file);
  - or a rule written out in the test from the input (state it in a comment/docstring).
  Write the derivation next to the assert. No golden JSON dumps of the server's own output, no magic numbers.
- Every new or changed test must be shown to FAIL on the fault it guards (fail-to-pass): apply the mutant / revert
  the fix in your worktree, run the test, see it fail, restore. Record each in `<S>\fix2\<your-name>\f2p.jsonl`
  (one JSON line: test, mutant description, file:line, result before/after). A test you could not make fail is not done.
- No skip/xfail, no approx unless the client itself rounds that way, no try/except that swallows, no mocks replacing
  the unit under test (monkeypatching time, random, paths, the save db is fine). Seed or pin randomness.
- If a test exposes a real difference between the server and the client/XML, fix the production code only when
  the bytecode/XML evidence is clear, keep the fix minimal, and note the evidence (Class.method, XML path) in the
  commit message and your report. When unsure, do not fix: report it.

## Running the tests (important: the server has a single-instance lock)
`empires-server.py` uses `tendo.singleton.SingleInstance()`, the lock name comes from `sys.argv[0]`. Every agent
must use its OWN launcher script at a unique path, otherwise runs collide with PermissionError:
  copy `<S>\denetim2\run_pytest_denetim2.py` to `<S>\fix2\<your-name>\run_pytest_<your-name>.py` and run
  `"<PY>" "<S>\fix2\<your-name>\run_pytest_<your-name>.py" -q -p no:cacheprovider [tests]` from your worktree root,
  with env `PYTHONUTF8=1 PYTHONIOENCODING=utf-8`. Never `python -m pytest` or `pytest.exe`.
Give any mutant run a timeout (a broken lock deadlocks: kill the process after ~10x the normal time, count it killed).
Do not use mutmut (its timeout does not work on Windows). `<S>\denetim2\mut_harness.py` / `targeted_mutants.py` are
examples of a working harness with timeouts.

## Safety
- `test\conftest.py` keeps the crash-log text editor from opening. Never run tests against code older than cb00c06.
  If any Notepad/vim window appears, stop and say so in your report.
- Never touch: `C:\Users\<user>\Desktop\Raise\TurkceOyun`, the main checkout
  `C:\Users\<user>\Desktop\Raise\raisetheempires-pr`, `<S>\mm`, `<S>\mm2`. Read-only use of the main
  checkout is fine. Never push, never touch remotes, never download anything.
- Line endings: CRLF files: empires-server.py, save_engine.py, battle_engine.py, game_settings.py, logger.py,
  state_machine.py, save_migration.py, test\battle_turn_test.py. Keep each file's existing endings (check with
  `file` or a byte count before editing). Use the Edit tool or a Python bytes script, never `sed -i`.
- Tests must not write into the repository folder (use tmp_path).

## Finishing
- Run the full suite (all of `test\`) with your launcher: everything must pass. Report the count and time.
- Commit in your worktree branch: `git -c core.autocrlf=false commit`, Turkish message, and NO attribution lines
  at all (no Co-Authored-By, no "Generated with"). Do not add `.log.txt.swp`, `log.txt`, `cache/`.
- Final report (English is fine, short): branch name and commit, what you changed per finding id (B-..),
  f2p evidence counts, any production fix with its evidence, anything left open and why, any file outside your brief
  you would have needed to change.

Paths: `<S>` = `<HOME>\AppData\Local\Temp\claude\44db76dc85e0ce87\6e027af0-22bc-435d-8563-59919183e99e\scratchpad`
`<PY>` = `C:\Users\<user>\Desktop\Raise\venv312\Scripts\python.exe`
