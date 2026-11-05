# docs/ holds reports and the evidence of the audits (docs/denetim/hesap/), among them old copies of test files that
# were measured there. They are not tests of the server: pytest run from the repository root (as CI runs it) does
# not collect anything here. The tests are in test/.
collect_ignore_glob = ["*"]
