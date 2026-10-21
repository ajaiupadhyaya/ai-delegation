.PHONY: all test lint data

all: lint test

test:
	uv run pytest -v

lint:
	uv run ruff check

data:
	uv run python -m aideleg.acquire
