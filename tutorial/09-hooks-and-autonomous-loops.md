# Урок 09. Lifecycle Hooks и автономные циклы `/poke`, `/improve`, `/refactor`

[← Урок 08. Ревью и контроль завершения](08-review-autoreview-and-judge.md) | [Карта курса](README.md) | [Урок 10. Headless CLI, песочницы и панели →](10-headless-sandboxes-and-panels.md)

## Цель урока

- Освоить детерминированные перехватчики среды выполнения (**Lifecycle Hooks**):
  - воротный хук **`pre_tool`** (блокировка запрещённых действий с кодом возврата `2` до их выполнения);
  - синхронный хук обратной связи **`post_tool_feedback`** (автоматическая подача вывода тестов/линтера прямо в результат инструмента для модели).
- Понять, как включать хуки **на уровне конкретного проекта** через переменные окружения `JCODE_HOOK_*` (в отличие от глобального `~/.jcode/config.toml`).
- Изучить встроенные автономные циклы доводки кода в `jcode`: **`/poke`** (`todo_gate_digest`), **`/improve`** и пакетный **`/refactor`**.
- Защитить чистоту `src/books_api/domain/` железными хуками и провести автономный рефакторинг публичного фасада домена.

---

## Теория-минимум: промпты просят, а хуки гарантируют

Инструкции в `AGENTS.md` соблюдаются моделью почти всегда, но в критичных местах (запрет трогать прод-конфиги, запрет тянуть внешние фреймворки в чистый домен, обязательный прогон быстрых тестов после правки) хочется **100% детерминированной гарантии на уровне рантайма**. Для этого в `jcode` встроены 8 точек Lifecycle Hooks:

- Наблюдатели (асинхронные, не задерживают ход): `session_start`, `session_end`, `turn_start`, `turn_end`, `post_tool`.
- Трансформер входа перед валидацией: `pre_tool_transform`.
- **Политика-ворота (`pre_tool`)**: запускается синхронно перед каждым вызовом тула, получает имя тула в `JCODE_HOOK_TOOL_NAME` и полный JSON аргументов в **stdin**:
  - `exit 0` разрешает вызов (либо может вернуть JSON с `"permissionDecision": "deny"` / `"updatedInput"`);
  - **`exit 2` блокирует вызов**, а текст из `stderr` возвращается модели как ошибка инструмента, чтобы агент сразу скорректировал поведение!
- **Обратная связь (`post_tool_feedback`)**: запускается синхронно после каждого успешного тула, получает `JCODE_HOOK_TOOL_NAME` и список затронутых файлов в `JCODE_HOOK_TOUCHED_PATHS` (по одному абсолютному пути на строку). Весь `stdout` скрипта автоматически приклеивается к результату тула под маркером `[post_tool_feedback]`.

### Как привязать хуки к конкретному проекту

Глобальная таблица `[hooks]` живёт в `~/.jcode/config.toml`, но переменные окружения **`JCODE_HOOK_*` всегда имеют наивысший приоритет** и выполняются в рабочей директории сессии (`JCODE_HOOK_CWD`). Поэтому проектные хуки кладут прямо в репозиторий (например, в `scripts/hooks/`) и запускают проектную сессию с `JCODE_HOOK_PRE_TOOL=...` и `JCODE_HOOK_POST_TOOL_FEEDBACK=...` (через `.envrc` / `direnv`, `Makefile` или короткий скрипт запуска).

### Автономные рабочие циклы: `/poke`, `/improve` и `/refactor`

Когда у проекта есть быстрая обратная связь от тестов, в полную силу раскрываются три встроенных цикла `jcode`:

1. **`/poke [on|off|status]`**: демон автоматически продолжает работу (до 3 попыток на неизменный список), если агент остановился при незакрытых `todo`. Дополнительно в `~/.jcode/config.toml` можно включить `[features] todo_gate_digest = true` для сводного напоминания о слабых местах перед закрытием цикла.
2. **`/improve [plan|status|resume|stop] [фокус]`**: автономный цикл поиска и внедрения улучшений. Команда `/improve plan <фокус>` сначала строит ранжированный список `todo` без редактирования файлов!
3. **`/refactor [plan|status|resume|stop] [фокус]`**: управляемый пакетный рефакторинг. Агент разбивает рефакторинг на небольшие безопасные батчи, валидирует каждый батч тестами и **автоматически зовёт независимого read-only сабагента проверить каждый значимый батч**.

---

## Практика шаг за шагом

### Шаг 1. Создайте два проектных хука в `scripts/hooks/`

Создайте папку `scripts/hooks/` и положите в неё два исполняемых скрипта.

**1. Воротный хук чистоты домена `scripts/hooks/domain_purity_gate.py`** (`pre_tool`):
Блокирует с кодом `2` попытки записать в `src/books_api/domain/` запрещённые внешние импорты (`fastapi`, `flask`, `sqlalchemy`, `sqlite3`, `requests`, `httpx`), а также запрещает вызывать сырой `pip install` через `bash`:

```python
#!/usr/bin/env python3
"""pre_tool gate: защищает архитектурную чистоту src/books_api/domain/."""
import json
import os
import re
import sys

tool = os.environ.get("JCODE_HOOK_TOOL_NAME", "")
raw = sys.stdin.read()
if not raw.strip():
    sys.exit(0)

data = json.loads(raw)

if tool == "bash":
    cmd = data.get("command", "")
    if re.search(r"(^|\s)pip3?\s+install\b", cmd):
        sys.stderr.write("Blocked by project hook: use 'uv add' instead of 'pip install'.\n")
        sys.exit(2)

if tool in {"write", "edit", "apply_patch"}:
    payload_text = json.dumps(data, ensure_ascii=False)
    if "src/books_api/domain/" in payload_text:
        forbidden = ("fastapi", "flask", "django", "sqlalchemy", "sqlite3", "httpx", "requests")
        for pkg in forbidden:
            if re.search(rf"\b(import\s+{pkg}|from\s+{pkg}\b)", payload_text):
                sys.stderr.write(
                    f"Blocked by domain_purity_gate: '{pkg}' is forbidden inside pure domain layer.\n"
                )
                sys.exit(2)

sys.exit(0)
```

**2. Хук мгновенного прогона тестов `scripts/hooks/pytest_feedback.sh`** (`post_tool_feedback`):
Если агент изменил любой `.py`-файл в `src/books_api/` или `tests/`, хук автоматически запускает `uv run pytest -q` и прикладывает результат прямо к ответу тула `write`/`edit`/`apply_patch`:

```bash
#!/usr/bin/env bash
case "${JCODE_HOOK_TOOL_NAME:-}" in
  write|edit|apply_patch) ;;
  *) exit 0 ;;
esac

run_tests=0
while IFS= read -r path; do
  case "$path" in
    *.py) run_tests=1 ;;
  esac
done <<<"${JCODE_HOOK_TOUCHED_PATHS:-}"

if [ "$run_tests" -eq 1 ]; then
  uv run pytest -q
fi
exit 0
```

Сделайте оба скрипта исполняемыми:

```bash
chmod +x scripts/hooks/domain_purity_gate.py scripts/hooks/pytest_feedback.sh
```

> **Обратите внимание на деталь документации `jcode`:** команда хука парсится в shell-стиле, но запускается напрямую без промежуточного `/bin/sh -c`, поэтому у обоих файлов обязательно должен быть шебанг (`#!/usr/bin/env ...`) и бит исполнения `chmod +x`.

### Шаг 2. Запустите `jcode` с проектными хуками и проверьте блокировку

Перезапустите клиент `jcode` в директории проекта с подключёнными переменными окружения:

```bash
JCODE_HOOK_PRE_TOOL="./scripts/hooks/domain_purity_gate.py" \
JCODE_HOOK_POST_TOOL_FEEDBACK="./scripts/hooks/pytest_feedback.sh" \
jcode
```

*(Если у вас уже крутится фоновый сервер `jcode` без этих переменных, для изолированной проверки проектных env-переменных удобно добавить временный сокет `--socket /tmp/books-hooks.sock`, тогда локальный демон гарантированно унаследует переменные окружения прямо из этой команды).*

Проверьте ворота `pre_tool` провокационным запросом:

```text
Для быстрого эксперимента добавь `import sqlite3` в начало файла `src/books_api/domain/catalog.py`, а если сработает защитный хук проекта, ничего не ломай и объясни причину блокировки.
```

Вы увидите в TUI, что вызов `edit` мгновенно заблокирован до изменения файла на диске с точным сообщением `Blocked by domain_purity_gate: 'sqlite3' is forbidden inside pure domain layer`!

### Шаг 3. Оцените `/improve plan` и проведите пакетный `/refactor`

Сначала проверим статус `/poke` и безопасно спланируем возможные улучшения домена без правок кода:

```text
/poke status
/improve plan консистентность доменных исключений, публичных экспортов и строгой типизации в src/books_api/domain
```

Посмотрите, какой ранжированный список точек роста составил агент в `/todos`. Если в любой момент захочется остановить автономный цикл на безопасной границе, используйте `/improve stop` (а для проверки состояния `/improve status`).

Теперь выполним чистовой пакетный рефакторинг публичного API нашего домена через **`/refactor`**:

```text
/refactor Приведи в идеальный порядок публичный фасад `src/books_api/domain/__init__.py` (явный отсортированный `__all__`), устрани любое дублирование проверок пустых строк между сущностями через компактный внутренний хелпер валидации и убедись, что все модули домена единообразно аннотированы.
```

Посмотрите на синергию двух механизмов:

1. После каждой правки `edit`/`apply_patch` ваш хук `post_tool_feedback` автоматически прогоняет `uv run pytest -q` и отдаёт статус тестов в `[post_tool_feedback]` без отдельного вызова `bash`.
2. Сам цикл `/refactor` делит работу на аккуратные шаги и вызывает независимого read-only сабагента для проверки каждого значимого батча!

По завершении рефакторинга сохраните скрипты хуков и обновлённый домен в Git:

```text
/commit
```

---

## Самопроверка

Проверьте работу воротного хука напрямую из терминала одной командой:

```bash
printf '{"command":"pip install fastapi"}' | JCODE_HOOK_TOOL_NAME=bash ./scripts/hooks/domain_purity_gate.py ; echo "exit=$?"
uv run pytest -q
```

Чеклист результата:

- [ ] Команда проверки `domain_purity_gate.py` печатает причину блокировки и выводит `exit=2`.
- [ ] Скрипт `pytest_feedback.sh` автоматически возвращает вывод `uv run pytest -q` при редактировании `.py`-файлов.
- [ ] В `src/books_api/domain/__init__.py` оформлен аккуратный `__all__`, а все тесты проекта проходят.

---

## Шпаргалка урока

| Переменная / Команда | Назначение |
|---|---|
| `JCODE_HOOK_PRE_TOOL` | Синхронный перехватчик перед тулом (`exit 0` разрешить, `exit 2` заблокировать с `stderr`) |
| `JCODE_HOOK_POST_TOOL_FEEDBACK` | Синхронный хук после тула: добавляет свой `stdout` в контекст модели как `[post_tool_feedback]` |
| `JCODE_HOOK_TOUCHED_PATHS` | Переменная окружения со списком затронутых тулом путей (по одному на строку) |
| `/poke [on\|off\|status]` | Автоматический дожим незавершённых пунктов `todo` на стороне демона |
| `/improve [plan\|status\|resume\|stop] <focus>` | Автономный цикл планирования и внедрения улучшений по выбранному фокусу |
| `/refactor [plan\|status\|resume\|stop] <focus>` | Безопасный пакетный рефакторинг с автотестами и ревью каждого батча сабагентом |

Следующий шаг: **[Урок 10. Неинтерактивный CLI `jcode run`, песочницы инструментов и живые панели →](10-headless-sandboxes-and-panels.md)**
