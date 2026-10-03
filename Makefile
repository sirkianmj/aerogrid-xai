.PHONY: help setup env-update test lint format dev-backend clean services-start services-stop services-status

help:
	@echo "AeroGrid-XAI -- available targets:"
	@echo "  setup        Create the conda environment"
	@echo "  env-update   Update the conda environment from environment.yml"
	@echo "  test         Run backend tests with coverage"
	@echo "  lint         Run ruff and mypy on backend"
	@echo "  format       Run ruff format on backend"
	@echo "  dev-backend  Start FastAPI dev server on :8000"
	@echo "  clean        Remove Python and Node caches"

setup:
	mamba env create -f environment.yml

env-update:
	mamba env update -f environment.yml --prune

test:
	cd backend && pytest --cov=app --cov-report=term-missing

lint:
	cd backend && ruff check . && mypy .

format:
	cd backend && ruff format .

dev-backend:
	cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache backend/.coverage backend/coverage.xml


services-start:
	bash scripts/start_services.sh

services-stop:
	bash scripts/stop_services.sh

services-status:
	bash scripts/status_services.sh
