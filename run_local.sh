#!/usr/bin/env bash
set -e
docker compose up -d
# optional: start backend venv if present
# source backend/venv/bin/activate || true
export RUN_INTEGRATION=1
PYTHONPATH=backend pytest -q backend/tests/test_integration_stack.py::test_end_to_end
