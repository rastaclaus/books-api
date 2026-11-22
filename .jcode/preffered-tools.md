# Предпочтительные инструменты для books-api

- Для поиска символов, классов и файлов по проекту всегда используй `agentgrep` (`mode="grep"`, `mode="find"`, `mode="outline"`), а не `grep`/`find` через `bash`.
- Для точечных правок существующих модулей используй `edit` или `apply_patch`, никогда не переписывай файлы через `python -c` или `sed` в `bash`.
- Для проверки качества и тестов используй рецепты `justfile`: `just check` (прогон `ruff check`, `ruff format --check` и `ty check`) и `just test` (короткий прогон `uv run pytest -q`), а для автоформатирования вызывай `just fmt`.

