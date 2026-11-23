# Урок 01. Рабочее пространство, TUI и живой контракт `AGENTS.md`

[← Карта курса](README.md) | [Урок 02. Конфигурация `opencode.jsonc` и `cli.json` →](02-project-config-models-and-formatters.md)

## Цель урока

- Освоить базовую навигацию и диагностику в OpenCode V2: клиент-серверную архитектуру (`opencode service status`, `opencode debug paths`, `opencode debug config`), палитру команд `Ctrl+P`, leader-ключ `Ctrl+X`, переключение моделей `/models` и агентов `/agents`, контекстные ссылки `@путь`, встроенный shell-режим `!`.
- Понять, как OpenCode собирает инструкции сессии и почему корневой файл **`./AGENTS.md`** служит живым командным контрактом проекта, который обновляется **на лету**, без перезапуска сессии.
- Задать архитектурные границы `books-api` и обязательные ворота качества (`just check` и `just test`) в `AGENTS.md`, убедиться, что агент их видит, настроить максимально строгий непротиворечивый контур `ruff` + `ty` + `pytest` с `justfile` и создать базовую иерархию `DomainError`.

---

## Теория-минимум: как `AGENTS.md` попадает в голову агента

При старте сессии OpenCode V2 собирает инструкции в таком порядке:

1. Системный промпт выбранного агента (`build` — кодинг, `plan` — планирование без правок, `general` и `explore` — сабагенты).
2. Отдельные гайды Code Mode, MCP, references и скиллов.
3. **`AGENTS.md`**: глобальный `~/.config/opencode/AGENTS.md` (если есть) и все `AGENTS.md` от корня проекта вверх до домашней директории.
4. Дополнительные инструкции из массива `instructions` в `opencode.jsonc` (Урок 02).
5. Динамические источники: вложенные `AGENTS.md`, обнаруженные при чтении файлов (Урок 04), скиллы, references.

Ключевая особенность OpenCode V2, отличающая его от многих других агентов:

- **`AGENTS.md` — живой документ.** Если вы отредактировали `AGENTS.md` в запущенной сессии, OpenCode обнаружит изменение и добавит обновление инструкций перед следующим запросом. Перезапускать сессию не нужно. (Исключение — вложенные `AGENTS.md` ниже рабочей директории: их правка после загрузки не отслеживается автоматически.)
- **`AGENTS.md` хранится в Git и разделяется со всей командой.** Туда пишут инварианты архитектуры, стек проекта, команды проверки качества (`just check`, `just test`) и жёсткие ограничения («чего делать нельзя»).
- **Клиент и сервер разделены.** TUI — это лишь клиент фонового сервера `opencode`, который владеет сессиями, конфигами и инструментами. Поэтому диагностикой (`opencode debug ...`, `opencode mcp list`, `opencode stats`) удобно пользоваться из второго терминала, не выходя из сессии.

---

## Практика шаг за шагом

### Шаг 1. Запустите OpenCode и осмотритесь

Откройте терминал в корне репозитория `books-api` и запустите агент:

```bash
opencode
```

Не отправляя обычных сообщений модели, осмотритесь в TUI:

- Нажмите `Ctrl+P` — откроется палитра всех доступных действий в текущем виде.
- Нажмите `Ctrl+X` (leader-ключ), затем `M` — откроется выбор модели (`/models`). Нажмите `Esc`, чтобы закрыть.
- Нажмите `Ctrl+X`, затем `A` — список агентов (`/agents`). Вы увидите встроенных: `build` (основной кодинг-агент), `plan` (планирование без правок файлов), `general` и `explore` (сабагенты). Вернуться к `build` можно `Shift+Tab`.
- Введите `@` в поле промпта — откроется поиск файлов. Введите `pyproject` и прикрепите `pyproject.toml`.
- Нажмите `Esc` на пустом промпте, введите `!git status` и нажмите `Enter` — это shell-режим: команда выполнится в рабочей директории сессии, а её вывод останется в истории.

### Шаг 2. Проверьте сервер и собранную конфигурацию из второго терминала

Во втором терминале в папке `books-api` выполните:

```bash
opencode service status     # адрес фонового сервера
opencode debug paths        # где OpenCode хранит данные, конфиги, БД
opencode debug config       # итоговую слитую конфигурацию
```

Обратите внимание: `opencode debug config` показывает, как глобальный `~/.config/opencode/opencode.jsonc` (если он есть) сливается с проектными файлами. Пока проектных настроек у нас нет — это поле для Урока 02.

### Шаг 3. Создайте проектный контракт `./AGENTS.md`

Попросим агента изучить стартовый репозиторий и создать `AGENTS.md` с чёткими границами учебного проекта. Отправьте в чат следующий промпт:

```text
Изучи текущую структуру репозитория и @pyproject.toml.
Создай в корне проекта файл AGENTS.md для учебного проекта books-api (каталог свободной раздачи электронных книг).

Зафиксируй в AGENTS.md следующие обязательные правила проекта:
1. Область разработки: мы реализуем ТОЛЬКО чистую доменную область в пакете `src/books_api/domain/`. Никаких HTTP-фреймворков (FastAPI/Flask), никаких ORM/SQL и внешних runtime-зависимостей (`dependencies = []` в `pyproject.toml`).
2. Стек и стиль: Python 3.14+, строгая типизация (аннотации типов везде, `dataclass(frozen=True, slots=True)` для Value Objects, `Enum` / `StrEnum`, `typing.Protocol` для портов репозиториев, `@override` при переопределении методов).
3. Управление пакетами: использовать исключительно `uv` (`uv add --dev pytest ruff ty`, запуск инструментов через `uv run ...` или рецепты `justfile`). Не вызывать голый `pip` или системные `pytest` / `ruff` / `ty` напрямую.
4. Обязательные ворота качества перед сдачей задачи: перед завершением любого задания агент ОБЯЗАН прогнать `just check` (линтер `ruff check`, проверка форматирования `ruff format --check` и строгий тайпчекер `ty check`) и `just test` (прогон `pytest`), добившись нулевого числа замечаний и зелёных тестов.
5. Доменные ошибки: любые нарушения бизнес-инвариантов домена должны выбрасывать осмысленные исключения, унаследованные от базового `DomainError`, а не общие `Exception` или `AssertionError`.
6. Код и идентификаторы пишем на английском, краткие пояснения в ответах пользователю даём на русском.
```

Дождитесь, пока агент прочитает `pyproject.toml` и запишет `AGENTS.md`.

### Шаг 4. Проверьте живое обновление инструкций

В отличие от агентов, фиксирующих системный промпт на старте сессии, OpenCode перечитывает `AGENTS.md` между запросами. Проведём эксперимент: прямо сейчас дополните `AGENTS.md` одной строкой (в редакторе или во втором терминале):

```bash
printf '\n- В ответах всегда указывай затронутые файлы списком в конце.\n' >> AGENTS.md
```

Теперь отправьте агенту любой мелкий вопрос, например:

```text
Кратко: что лежит в src/books_api/__init__.py?
```

В транскрипте сессии вы увидите блок `AGENTS.md changes` (обновление инструкций), вставленное перед вашим запросом, — а в ответе появится список затронутых файлов, хотя вы об этом не просили в самом сообщении. Живой контракт работает без перезапуска сессии.

### Шаг 5. Первая боевая задача: строгие `ruff` + `ty`, `justfile` и иерархия `DomainError`

Проверим, как агент следует только что принятому контракту, и сразу выстроим максимально строгий, но непротиворечивый контур проверок:

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
4. Создай стартовый фундамент доменного слоя: базовое исключение `DomainError` и специализированные ошибки `ValidationError`, `InvalidBookStateError`, `LicenseViolationError` и `QuotaExceededError`, экспортируй их в `src/books_api/domain/__init__.py` с явным `__all__` и напиши первые юнит-тесты.
Перед завершением прогони `just check` и `just test`.
```

Понаблюдайте за действиями агента в TUI:

- Агент сам положит код в `src/books_api/domain/` (например, `src/books_api/domain/errors.py` и `__init__.py`), потому что прочитал `AGENTS.md`.
- Для установки пакетов он использует `uv add --dev pytest ruff ty`, не трогая `dependencies = []` в `pyproject.toml`.
- Перед тем как сдать задачу, агент сам вызовет `just check` и `just test`: любые огрехи форматирования, импортов или аннотаций типов мгновенно отсекаются связкой `ruff` (`ALL`) и `ty` (`all = "error"`).
- В конце ответа агент перечислит затронутые файлы — это правило из Шага 4 продолжает работать в каждой новой сессии, потому что теперь живёт в `AGENTS.md`.

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

### Шаг 6. Зафиксируйте первый этап

Попросите агента сделать аккуратный коммит:

```text
Проанализируй git status и git diff, создай осмысленный коммит в стиле Conventional Commits со всеми изменениями: AGENTS.md, justfile, pyproject.toml, uv.lock, src/books_api/domain/ и tests/.
```

> **Заметка на будущее:** в Уроке 05 мы оформим этот ритуал в собственную slash-команду `/commit` — и до конца курса будем коммититься одной командой.

---

## Самопроверка

Выполните в терминале (или через `!`-команду / второй терминал):

```bash
just check
just test
git log -n 2 --oneline
opencode debug config | grep -A3 instructions || true
```

Чеклист результата:

- [ ] В корне лежат `AGENTS.md` и `justfile`, и вы увидели в живой сессии, как правка `AGENTS.md` подхватилась без перезапуска (блок `AGENTS.md changes` перед следующим запросом).
- [ ] В `pyproject.toml` список `dependencies` остался пустым (`[]`), а `pytest`, `ruff` и `ty` добавлены в dev-зависимости (`[dependency-groups]`) и строго сконфигурированы без конфликтов между форматтером, линтером и тайпчекером.
- [ ] В `src/books_api/domain/` создана иерархия `DomainError` (`DomainError`, `ValidationError`, `InvalidBookStateError`, `LicenseViolationError`, `QuotaExceededError`), и обе команды `just check` и `just test` завершаются с кодом `0`.

---

## Шпаргалка урока

| Команда / Файл | Назначение |
|---|---|
| `./AGENTS.md` | Живой проектный контракт для всех агентов в репозитории (коммитится в Git, обновляется между запросами без перезапуска сессии) |
| `./justfile` (`just check`, `just test`) | Единые ворота качества проекта (`ruff` + `ty` + `pytest`) перед сдачей задач |
| `opencode service status` | Адрес и состояние фонового сервера, владеющего сессиями и конфигами |
| `opencode debug paths` / `debug config` | Локальные пути хранения и итоговая слитая конфигурация |
| `Ctrl+P` | Палитра всех действий текущего вида |
| `Ctrl+X` + `M` / `A` | Выбор модели (`/models`) и агента (`/agents`); `Shift+Tab` — циклическое переключение агентов |
| `@путь` | Прикрепление файла или каталога к промпту (с поддержкой `@файл#20-45` для строк) |
| `!команда` (shell-режим) | Выполнить shell-команду в рабочей директории сессии, вывод остаётся в истории |

Следующий шаг: **[Урок 02. Конфигурация `opencode.jsonc` vs `cli.json`, варианты моделей, форматтеры и warming →](02-project-config-models-and-formatters.md)**
