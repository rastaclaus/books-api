default: check test

check:
    uv run ruff check .
    uv run ruff format --check .
    uv run ty check

fmt:
    uv run ruff check --fix .
    uv run ruff format .

test *args:
    uv run pytest -q {{args}}
