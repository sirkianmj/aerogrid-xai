.PHONY: help setup test lint dev-backend clean

help:
	@echo "AeroGrid-XAI -- available targets:"
	@echo "  setup        Create or update the conda environment"
	@echo "  test         Run backend tests with coverage"
	@echo "  lint         Run flake8 and mypy on backend"
	@echo "  dev-backend  Start FastAPI dev server on :8000"
	@echo "  clean        Remove Python and Node caches"

setup:
	mamba env create -f environment.yml || mamba env update -f environment.yml

test:
	cd backend && pytest --cov=api --cov-report=term-missing

lint:
	cd backend && flake8 . && mypy .

dev-backend:
	cd backend && uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/.pytest_cache backend/.mypy_cache backend/.coverage backend/coverage.xml
