#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON:-.venv/bin/python}"
TORTUS_BIN="${TORTUS_CLI:-.venv/bin/tortus}"

if [ ! -x "$TORTUS_BIN" ]; then
  python3 -m venv .venv
  "$PYTHON_BIN" -m pip install -e '.[dev]'
fi

"$TORTUS_BIN" ingest --corpus engineering
"$TORTUS_BIN" index --layout torus
"$TORTUS_BIN" query \
  "How did the token migration incident connect authentication and tracing?" \
  --explain
"$TORTUS_BIN" golden-set --out data/golden_set.json --count 100
"$TORTUS_BIN" eval --suite benchmark --strategies all \
  --json-out data/eval/benchmark.json \
  --duckdb-out data/eval/results.duckdb
"$TORTUS_BIN" report \
  --eval-json data/eval/benchmark.json \
  --out data/reports/eval-report.md

echo
echo "Report: data/reports/eval-report.md"
echo "Dashboard: $TORTUS_BIN serve --port 8010"
