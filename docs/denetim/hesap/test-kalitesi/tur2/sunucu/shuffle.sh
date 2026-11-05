#!/bin/sh
# full suite in shuffled (11, 22, 33) and reverse order, with the audit's shuffle plugin
R=<S>/fix2/sunucu
for seed in ${SEEDS:-11 22 33 reverse}; do
  echo "== SHUFFLE_SEED=$seed"
  SHUFFLE_SEED=$seed sh $R/rt.sh test -p denetim2_shuffle -p no:warnings "$@" 2>&1 | grep -E "^\[shuffle\]|passed|failed|error|changed files|^  [a-zA-Z]" | tail -8
done
