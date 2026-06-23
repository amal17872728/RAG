VENV=backend/venv
PY=python3

.PHONY: test coverage run-backend run-uvicorn start-qdrant

test:
	# Run pytest (ensure virtualenv is activated or use system python)
	PYTHONPATH=backend pytest -q

coverage:
	PYTHONPATH=backend coverage run -m pytest
	coverage report -m
	coverage html

run-backend:
	# Start backend with uvicorn (assumes venv activated)
	cd backend && $(PY) -m uvicorn app.main:app --reload

run-uvicorn:
	# Alias for run-backend
	$(MAKE) run-backend

start-qdrant:
	# Start qdrant with docker (if docker is available)
	docker run -d --name qdrant -p 6333:6333 qdrant/qdrant
