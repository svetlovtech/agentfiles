.PHONY: lint test check clean build install

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/
	mypy src/

test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --tb=short --cov=syncode --cov-report=term-missing

check: lint test

build:
	python -m build

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache

install:
	pip install -e ".[dev]"
