# Урок 01. Контракт проекта в `AGENTS.md` и инспекция контекста

[← Назад к карте курса](README.md) | [Урок 02. Проектные оверлеи и prompt-кэш →](02-prompt-overlays-and-cache.md)

## Цель урока

- Освоить базовую навигацию и команды инспекции в TUI `jcode`: `/help`, `/model`, `/info`, `/context`, `/git`, `/commit`.
- Понять, как `jcode` собирает системный промпт сессии и почему корневой файл **`./AGENTS.md`** служит главным командным контрактом проекта.
- Задать архитектурные границы `books-api` и обязательные ворота качества (`just check` и `just test`) в `AGENTS.md`, убедиться через `/context`, что агент их видит, настроить максимально строгий непротиворечивый контур `ruff` + `ty` + `pytest` с `justfile` и создать базовую иерархию `DomainError`.

---

## Теория-минимум: как `AGENTS.md` попадает в голову агента

При старте новой сессии `jcode` собирает системный промпт из нескольких слоёв по порядку:

1. Встроенный базовый системный промпт (или его замена в `.jcode/system-prompt.md`).
2. Модули возможностей (например, поддержка встроенных диаграмм `mermaid`).
3. **`AGENTS.md`**: проектный `./AGENTS.md` из рабочей директории и глобальный `~/AGENTS.md`.
4. Проектные и глобальные оверлеи (`.jcode/prompt-overlay.md` и `.jcode/preferred-tools.md`, их мы изучим в Уроке 02).
5. Динамический хвост: активные воспоминания (`memory`) и загруженный скилл (`skill`).

Два критически важных правила:

- **`AGENTS.md` хранится в Git и разделяется со всей командой.** Туда пишут инварианты архитектуры, стек проекта, команды проверки качества (`just check`, `just test`) и жёсткие ограничения («чего делать нельзя»).
- **Слои промпта фиксируются при создании сессии.** Если вы создали или отредактировали `./AGENTS.md`, уже запущенная сессия сохранит старый снимок промпта (чтобы не ломать prompt-кэш посреди диалога). Чтобы изменения вступили в силу, начните новую сессию (`/clear` или перезапуск `jcode`).

---

## Практика шаг за шагом

### Шаг 1. Запустите `jcode` и осмотритесь в текущей сессии

Откройте терминал в корне репозитория `books-api` и запустите агент:

```bash
jcode
```

Не отправляя обычных сообщений модели, выполните по очереди четыре служебные slash-команды (они выполняются мгновенно и не тратят токены генерации):

```text
/help
/info
/git
/context
```

Что посмотреть в выводе:

- `/info` покажет текущего провайдера, выбранную модель (поменять её в любой момент можно через `/model`), ID сессии и счётчики токенов.
- `/git` покажет краткий `git status --short --branch` рабочей директории на стороне сервера `jcode`.
- `/context` раскроет полный собранный системный промпт, список активных инструментов и метаданные окна контекста. Обратите внимание: сейчас в секции проектных инструкций ещё нет правил `books-api`.

### Шаг 2. Создайте проектный контракт `./AGENTS.md`

Попросим `jcode` самостоятельно изучить стартовый репозиторий и создать `AGENTS.md` с чёткими границами нашего учебного проекта. Отправьте в чат следующий промпт:

```text
Изучи текущую структуру репозитория и pyproject.toml.
Создай в корне проекта файл AGENTS.md для учебного проекта books-api (каталог свободной раздачи электронных книг).

Зафиксируй в AGENTS.md следующие обязательные правила проекта:
1. Область разработки: мы реализуем ТОЛЬКО чистую доменную область в пакете `src/books_api/domain/`. Никаких HTTP-фреймворков (FastAPI/Flask), никаких ORM/SQL и внешних runtime-зависимостей (`dependencies = []` в `pyproject.toml`).
2. Стек и стиль: Python 3.14+, строгая типизация (аннотации типов везде, `dataclass(frozen=True, slots=True)` для Value Objects, `Enum` / `StrEnum`, `typing.Protocol` для портов репозиториев, `@override` при переопределении методов).
3. Управление пакетами: использовать исключительно `uv` (`uv add --dev pytest ruff ty`, запуск инструментов через `uv run ...` или рецепты `justfile`). Не вызывать голый `pip` или системные `pytest` / `ruff` / `ty` напрямую.
4. Обязательные ворота качества перед сдачей задачи: перед завершением любого задания агент ОБЯЗАН прогнать `just check` (линтер `ruff check`, проверка форматирования `ruff format --check` и строгий тайпчекер `ty check`) и `just test` (прогон `pytest`), добившись нулевого числа замечаний и зелёных тестов.
5. Доменные ошибки: любые нарушения бизнес-инвариантов домена должны выбрасывать осмысленные исключения, унаследованные от базового `DomainError`, а не общие `Exception` или `AssertionError`.
6. Код и идентификаторы пишем на английском, краткие пояснения в ответах пользователю даём на русском.
```

Дождитесь, пока `jcode` прочитает `pyproject.toml` и запишет `AGENTS.md`.

### Шаг 3. Активируйте обновлённый системный промпт и проверьте `/context`

Помните правило о снимке системного промпта на старте сессии? Выйдите из текущей сессии (`Ctrl+D` или `/clear`, либо откройте новую сессию `jcode` в этой же папке) и сразу введите:

```text
/context
```

Найдите в выводе `/context` подключённый блок `./AGENTS.md`. Теперь каждая новая сессия (и каждый будущий воркер в проекте) с первого же хода знает правила `books-api` без повторных объяснений в промптах.

### Шаг 4. Первая боевая задача: строгие `ruff` + `ty`, `justfile` и иерархия `DomainError`

Проверим, как агент следует только что принятому контракту, и сразу выстроим в проекте максимально строгий, но непротиворечивый контур проверок (`ruff`, `ty`, `pytest`, `justfile`):

```text
1. Подключи dev-зависимости `pytest`, `ruff` и `ty` (оставив runtime-зависимости пустыми).
2. Настрой в `pyproject.toml` `pytest`, `ruff` и `ty` под Python 3.14 максимально строго, но без взаимных противоречий:
   - в `[tool.ruff]`: `target-version = "py314"`, `line-length = 120`, `src = ["src", "tests"]`;
   - в `[tool.ruff.lint]`: `select = ["ALL"]` с точечным `ignore` для правил, конфликтующих с `ruff format`, друг с другом, Python 3.14 или русскоязычным контекстом (`COM812`, `ISC001`, `D203`, `D213`, `CPY001`, `D`, `RUF001`, `RUF002`, `RUF003`, `EM101`, `EM102`, `TRY003`, `TC001`, `TC002`, `TC003`), плюс разумные `per-file-ignores`: `T201` для `src/books_api/__init__.py`, `S101`, `PLR2004`, `SLF001`, `FBT003`, `INP001` для `tests/**`, а также `EXE001`, `INP001`, `T201` для будущих утилит в `tools/**` и `scripts/**`;
   - в `[tool.ty]`: `environment.python-version = "3.14"`, `terminal.error-on-warning = true`, `rules = { all = "error" }` и override для `tests/**` с `dynamic-function-decorator-return = "ignore"` (для декораторов `@pytest.mark.parametrize` и фикстур).
3. Создай в корне `justfile` с рецептами:
   - `default: check test`;
   - `check` (`uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check`);
   - `fmt` (`uv run ruff check --fix .` и `uv run ruff format .`);
   - `test *args` (`uv run pytest -q {{args}}`).
4. Создай стартовый фундамент доменного слоя: базовое исключение `DomainError` и специализированные ошибки `InvalidBookStateError`, `LicenseViolationError` и `QuotaExceededError`, экспортируй их в `src/books_api/domain/__init__.py` с явным `__all__` и напиши первые юнит-тесты.
Перед завершением прогони `just check` и `just test`.
```

Понаблюдайте за действиями агента в TUI:

- Агент сам положит код в `src/books_api/domain/` (например, `src/books_api/domain/errors.py` и `__init__.py`), потому что прочитал `AGENTS.md`.
- Для установки пакетов он использует `uv add --dev pytest ruff ty`, не трогая `dependencies = []` в `pyproject.toml`.
- Перед тем как сдать задачу, агент сам вызовет `just check` и `just test`: любые огрехи форматирования, импортов или аннотаций типов мгновенно отсекаются связкой `ruff` (`ALL`) и `ty` (`all = "error"`).

<details>
<summary>Эталонный ориентир для <code>justfile</code> и секций <code>[tool.*]</code> в <code>pyproject.toml</code> (нажмите, чтобы сверить)</summary>

**`justfile`:**
```just
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
```

**Ключевые секции `pyproject.toml`:**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-q --strict-markers --strict-config"

[tool.ruff]
target-version = "py314"
line-length = 120
src = ["src", "tests"]

[tool.ruff.lint]
select = ["ALL"]
ignore = [
    "COM812", "ISC001",        # конфликтуют с ruff format
    "D203", "D213", "D",       # конфликтующие/избыточные правила docstrings
    "CPY001",                  # без обязательных copyright-шапок
    "RUF001", "RUF002", "RUF003", # кириллица в строках/комментариях
    "EM101", "EM102", "TRY003",   # лаконичные сообщения в raise DomainError(...)
    "TC001", "TC002", "TC003",    # в Python 3.14 (PEP 649) аннотации ленивые по умолчанию
]

[tool.ruff.lint.per-file-ignores]
"src/books_api/__init__.py" = ["T201"]
"tests/**" = ["S101", "PLR2004", "SLF001", "FBT003", "INP001"]
"tools/**" = ["EXE001", "INP001", "T201"]
"scripts/**" = ["EXE001", "INP001", "T201"]

[tool.ruff.lint.isort]
known-first-party = ["books_api"]

[tool.ty.environment]
python-version = "3.14"

[tool.ty.terminal]
error-on-warning = true

[tool.ty.rules]
all = "error"

[[tool.ty.overrides]]
include = ["tests/**"]

[tool.ty.overrides.rules]
dynamic-function-decorator-return = "ignore"
```
</details>

### Шаг 5. Сохраните первый этап через `/commit`

В `jcode` встроена быстрая prompt-команда для аккуратного оформления коммита. Введите в TUI:

```text
/commit
```

Агент проверит `git status` и `git diff`, сформирует осмысленное сообщение коммита и зафиксирует `AGENTS.md`, `justfile`, обновлённый `pyproject.toml`, `uv.lock`, `src/books_api/domain/` и `tests/`.

---

## Самопроверка

Выполните в терминале (или через `!`-команду / второй терминал):

```bash
just check
just test
git log -n 2 --oneline
```

Чеклист результата:

- [ ] В корне лежат `AGENTS.md` и `justfile`, а команда `/context` в новой сессии показывает содержимое `AGENTS.md` внутри системного промпта.
- [ ] В `pyproject.toml` список `dependencies` остался пустым (`[]`), а `pytest`, `ruff` и `ty` добавлены в dev-зависимости (`[dependency-groups]`) и строго сконфигурированы без конфликтов между форматтером, линтером и тайпчекером.
- [ ] В `src/books_api/domain/` создана иерархия `DomainError`, и обе команды `just check` и `just test` завершаются с кодом `0`.

---

## Шпаргалка урока

| Команда / Файл | Назначение |
|---|---|
| `./AGENTS.md` | Проектный контракт для всех агентов в репозитории (коммитится в Git) |
| `./justfile` (`just check`, `just test`) | Единые ворота качества проекта (`ruff` + `ty` + `pytest`) перед сдачей задач |
| `/context` | Показать собранный системный промпт, активные тулы и размер контекста (без вызова LLM) |
| `/info` | Показать провайдера, модель, ID сессии и статистику токенов |
| `/model` | Открыть интерактивный переключатель провайдера и модели |
| `/git` | Быстрый просмотр `git status --short --branch` |
| `/commit` | Поручить агенту проанализировать изменения и создать аккуратный Git-коммит |

Следующий шаг: **[Урок 02. Проектные оверлеи `.jcode/` и работа с prompt-кэшем →](02-prompt-overlays-and-cache.md)**
