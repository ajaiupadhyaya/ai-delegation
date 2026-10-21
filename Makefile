.PHONY: all test lint

all: lint test

test:
	uv run pytest -v

lint:
	uv run ruff check
