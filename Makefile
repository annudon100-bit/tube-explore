.PHONY: build test shell lint typecheck check format clean install-hooks

build:
	docker compose build

test:
	docker compose run --rm -v $(PWD):/app tube-explore python -m pytest tests/ -v

shell:
	docker compose run --rm tube-explore bash

lint:
	docker run --rm -v $(PWD):/app tube-explore-tube-explore ruff check /app/tube_explore/ /app/tests/

typecheck:
	docker run --rm -v $(PWD):/app tube-explore-tube-explore mypy /app/tube_explore/

format:
	docker run --rm -v $(PWD):/app tube-explore-tube-explore ruff format /app/tube_explore/ /app/tests/

check: lint typecheck test

install-hooks:
	pip install pre-commit
	pre-commit install

clean:
	rm -rf __pycache__ .pytest_cache *.egg-info
	find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete
