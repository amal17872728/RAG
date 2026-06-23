#!/usr/bin/env bash
set -e

if [ ! -f .env ]; then
  echo "Missing .env. Copy .env.example to .env and fill in local values first."
  echo "See README.md for a ready-to-use local example."
  exit 1
fi

docker compose up --build -d
export RUN_INTEGRATION=1
PYTHONPATH=backend pytest -q backend/tests/test_integration_stack.py::test_real_stack_root_and_ollama
