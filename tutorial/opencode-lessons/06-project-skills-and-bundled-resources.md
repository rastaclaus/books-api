# Урок 06. Проектные скиллы `.opencode/skills/` со справочниками и скриптами

[← Урок 05. Кастомные slash-команды и shell-инъекции](05-custom-commands-and-shell-injection.md) | [Карта курса](README.md) | [Урок 07. Проектный MCP-сервер и Code Mode →](07-mcp-servers-and-code-mode.md)

## Цель урока

- Понять отличие **Commands** от **Skills** в OpenCode V2: команда — это шаблон промпта, который вы сами запускаете через `/cmd` и текст подставляется в чат; скилл — это лениво загружаемый **самим агентом** пакет экспертизы через тул `skill`, который OpenCode «рекламирует» модели только когда он релевантен по `description`.
- Освоить структуру многофайлового скилла: `.opencode/skills/<skill-id>/SKILL.md` (или плоский `skills/<name>.md`) с приватными подпапками `references/` и `scripts/` рядом, пути внутри скилла относительны каталогу `SKILL.md`.
- Настроить управление видимостью скиллов через frontmatter (`name`, `description`, `metadata.opencode/autoinvoke: false` / `disable-model-invocation`) и permissions (`action: "skill"`).
- Создать для `books-api` скилл `domain-invariants` — чеклист доменных инвариантов + справочник DDD-проверок + самопроверочный AST-скрипт чистоты домена, и укрепить граничные инварианты `Book` и `Reader`.

---

## Теория-минимум: Commands vs Skills и правила обнаружения скиллов

### Commands и Skills — два разных механизма

| | Commands (Урок 05) | Skills (этот урок) |
|---|---|---|
| Что это | Markdown-шаблон промпта | Пакет инструкций/файлов экспертизы |
| Кто запускает | **Вы**, через `/команда` | **Агент**, вызовом тула `skill` |
| Когда попадает в контекст | Сразу, текстом в сообщение | Лениво: только тело SKILL.md, по требованию модели |
| Как агент о нём узнаёт | Через палитру команд | OpenCode на каждом шаге модели перечисляет **ID + name + description** скиллов |
| Многофайловость | Нет (только шаблон) | Да: `references/`, `scripts/`, шаблоны рядом с SKILL.md |

Ключевая идея скиллов: **не добавлять каждую инструкцию в каждый промпт**. На каждом шаге модели OpenCode показывает только список (ID, name, description) разрешённых скиллов, у которых есть `description`; когда описание скилла совпадает с текущей задачей, модель сама подгружает его вызовом тула `skill` с точным ID. Полное тело Markdown и список (до 10) поддерживающих файлов попадают в контекст только в момент загрузки; содержимое `references/` и `scripts/` агент читает отдельно, когда скилл ему это предписывает.

### Где OpenCode ищет скиллы

| Scope | Источники |
|---|---|
| Проект | `.opencode/skills` |
| Совместимость (проект) | `.claude/skills`, `.agents/skills` |
| Глобально | `~/.config/opencode/skills` |
| Совместимость (глобально) | `~/.claude/skills`, `~/.agents/skills` |

Для проектных источников OpenCode ищет от текущей директории вверх до корня проекта и включает совпадающие каталоги на каждом уровне. Дополнительные локальные каталоги или HTTP-каталоги добавляются массивом `skills` в любом `opencode.json`/`opencode.jsonc` (массивы из всех найденных конфигов **комбинируются**, а не заменяются):

```jsonc
{
  "skills": [
    "./team-skills",
    "~/shared/opencode-skills",
    "https://example.com/opencode/skills/",
  ],
}
```

Внутри одного источника допустимы две формы:

```text
skills/
├── review.md                      # плоский скилл, ID = review
└── git-release/
    └── SKILL.md                   # каталог с SKILL.md, ID = git-release
```

Файлы с именем ровно `SKILL.md` можно вкладывать в группирующие каталоги (например `skills/teams/release/SKILL.md`); каталог с `SKILL.md` — это **один** скилл, глубже OpenCode внутри него скиллы не ищет. Скрытые файлы и `node_modules` пропускаются; поиск идёт не глубже шести уровней от корня источника.

**ID скилла определяет путь файла**, а не `name` из frontmatter: для `.opencode/skills/domain-invariants/SKILL.md` ID — `domain-invariants`. ID чувствителен к регистру; для переносимых скиллов рекомендуется нижний регистр в kebab-case (`^[a-z0-9]+(-[a-z0-9]+)*$`, 1–64 символов), совпадающий с именем каталога. Если два источника определяют один ID, загружается скилл из источника, зарегистрированного позже (проектные `.opencode/skills` переопределяют глобальные).

### Frontmatter и управление видимостью

```markdown
---
name: Git Release
description: Prepare a repository release
metadata:
  opencode/autoinvoke: false
---
```

| Поле | Поведение |
|---|---|
| `name` | Отображаемое имя; по умолчанию — ID из пути |
| `description` | Краткое описание, по которому модель видит скилл; **скиллы без `description` не рекламируются** |
| `metadata.opencode/autoinvoke: false` | Убрать скилл из списка доступных модели |
| `disable-model-invocation: true` | Тот же эффект, что `opencode/autoinvoke: false` |

Важно: `opencode/autoinvoke: false` лишь скрывает скилл из автосписка — скилл остаётся зарегистрированным, и явная загрузка по ID (например, промптом `@skill-id`) всё равно работает. Если заданы и `disable-model-invocation`, и `opencode/autoinvoke`, побеждает `opencode/autoinvoke`.

### Permissions для скиллов

Загрузка скиллов ограничивается permission-действием `skill` с ресурсом-скилл-ID. Правила выполняются по порядку, «последнее совпадение побеждает»:

```jsonc
{
  "permissions": [
    { "action": "skill", "resource": "*", "effect": "allow" },
    { "action": "skill", "resource": "internal-*", "effect": "deny" },
    { "action": "skill", "resource": "experimental-*", "effect": "ask" },
  ],
}
```

- `allow` — рекламирует и загружает без подтверждения;
- `ask` — рекламирует, но спрашивает перед загрузкой;
- `deny` — скрывает от модели и отклоняет загрузку.

---

## Практика шаг за шагом

### Шаг 1. Создайте многофайловый скилл `domain-invariants`

Попросите агента собрать каркас скилла с чеклистом инвариантов домена `books-api`:

```text
Создай многофайловый проектный скилл в `.opencode/skills/domain-invariants/` со следующей структурой:

.opencode/skills/
└── domain-invariants/
    ├── SKILL.md
    ├── references/
    │   └── ddd-checklist.md
    └── scripts/
        └── check_purity.py

Файл SKILL.md с frontmatter:

---
name: Domain Invariants
description: Аудит доменного слоя books-api: проверка неизменяемости Value Objects, защиты коллекций от внешней мутации, нормализации строк и граничных чисел, чистоты домена (без сетевых/БД/файловых импортов) и полноты параметризованных граничных тестов. Используй при работе над сущностями, Value Objects, инвариантами и тестами src/books_api/domain/.
---

Тело SKILL.md — рабочий чеклист из 5 пунктов, которые агент обязан пройти при аудите любой сущности или VO:
1. Защита коллекций от внешней мутации: внутренние коллекции (например, авторы книги, файлы книги) должны храниться как tuple/frozenset и не отдавать наружу мутабельные ссылки.
2. Нормализация строк: перед сохранением вызывать .strip(); строка только из пробелов (или пустая) должна выбрасывать осмысленный DomainError, а не сохраняться.
3. Граничные числа: size_bytes у BookAsset строго > 0; daily_quota у Reader >= 0; попытка задать вне диапазона — DomainError.
4. Чистота домена: в src/books_api/domain/ запрещены сетевые, БД и файловые импорты (fastapi, flask, django, sqlalchemy, sqlite3, httpx, requests) и print.
5. Матрица граничных тестов: для каждого подкласса DomainError (ValidationError, InvalidBookStateError, LicenseViolationError, QuotaExceededError) — @pytest.mark.parametrize с граничными значениями; финал аудита — обязательный прогон just check и just test и итоговая таблица «Модуль | Проверенный инвариант | Статус».

В SKILL.md после чеклиста явно предпиши: «Расширенную матрицу проверок VO/Entity/Aggregate читай в references/ddd-checklist.md; автоматическую проверку чистоты запусти командой `python3 scripts/check_purity.py` из каталога скилла».
```

После выполнения агента проверьте структуру и содержимое:

```bash
find .opencode/skills/domain-invariants -type f
cat .opencode/skills/domain-invariants/SKILL.md
```

Обратите внимание: `references/` и `scripts/` — **приватные** подпапки скилла. OpenCode не загружает их содержимое автоматически: при загрузке скилла агент получает каталог `SKILL.md` и выборку до десяти путей файлов рядом, а читает файлы только тогда, когда тело скилла ему это предписывает. Все пути, написанные внутри SKILL.md, отсчитываются от каталога скилла.

### Шаг 2. Расширенный справочник `references/ddd-checklist.md`

Просим агента наполнить справочник:

```text
Создай файл .opencode/skills/domain-invariants/references/ddd-checklist.md — расширенная матрица проверок для трёх категорий нашей модели books-api:

1. Value Objects (BookFormat, LanguageCode, ISBN, BookAsset, LicenseType): frozen=True + slots=True, валидация в __post_init__, нормализация строк перед валидацией, отрицательные/нулевые числовые значения отбрасываются DomainError, хэшируемость для использования как ключей dict.
2. Entities и Aggregate Root (Author, Book, Reader): защита инвариантов во всех мутирующих методах, коллекции как tuple, жизненный цикл Book (draft -> published -> withdrawn) не допускает недопустимых переходов без InvalidBookStateError, Reader.can_download проверяет is_verified и daily_quota.
3. Domain Services (DownloadService): не хранит состояние, все зависимости через typing.Protocol, все нарушения бизнес-правил через конкретные подклассы DomainError.

Для каждой строки матрицы приведи короткий пример параметризованного pytest-теста (@pytest.mark.parametrize на граничные значения: пустая строка, "   ", 0, -1,sys.maxsize).
```

### Шаг 3. AST-скрипт чистоты `scripts/check_purity.py`

Теперь — самопроверочный скрипт, который скилл предписывает запускать. Он должен быть самодостаточным (только stdlib, Python 3.14) и проходить наш строгий контур `ruff` без единого `noqa`:

```text
Создай файл .opencode/skills/domain-invariants/scripts/check_purity.py — самодостаточный AST-скрипт на чистом Python 3.14 (только stdlib, полная типизация, проходит ruff с select=ALL без noqa, никакого try/except pass, никаких print — вывод через sys.stdout.write/sys.stderr.write).

Скрипт делает:
1. Обходит все *.py файлы в src/books_api/domain/.
2. AST-анализом находит нарушения:
   - запрещённые импорты (import и from-import): fastapi, flask, django, sqlalchemy, sqlite3, httpx, requests;
   - вызовы print(...) (вывод отчёта реализуем через sys.stdout.write);
   - мутабельные дефолтные аргументы функций (литералы list/dict/set в значениях по умолчанию).
3. Каждое нарушение печатает строкой вида `<путь>:<строка> <описание>`; при отсутствии нарушений печатает "Domain purity: OK (N files checked)".
4. Выходной код: 0 — чисто, 1 — есть нарушения.

Пример каркаса аргументов: путь до каталога домена берём из sys.argv[1] со значением по умолчанию "src/books_api/domain" (не используя мутабельные дефолты и argparse без нужды).
После создания: сделай файл исполняемым (chmod +x) и прогони `python3 .opencode/skills/domain-invariants/scripts/check_purity.py` и `just check`, добившись чистоты.
```

<details>
<summary>Эталонный ориентир <code>check_purity.py</code> (нажмите, чтобы сверить)</summary>

```python
#!/usr/bin/env python3
"""AST-аудит чистоты доменного слоя books-api (только stdlib, Python 3.14+)."""

import ast
import sys
from pathlib import Path

BANNED_MODULES: frozenset[str] = frozenset(
    {"fastapi", "flask", "django", "sqlalchemy", "sqlite3", "httpx", "requests"}
)

MUTABLE_LITERALS: dict[type[ast.expr], str] = {
    ast.List: "list",
    ast.Dict: "dict",
    ast.Set: "set",
}


def report(message: str) -> None:
    sys.stdout.write(message + "\n")


def check_imports(tree: ast.Module, path: Path) -> list[str]:
    issues: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            issues.extend(
                f"{path}:{node.lineno} banned import '{alias.name}'"
                for alias in node.names
                if alias.name.split(".")[0] in BANNED_MODULES
            )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.split(".")[0] in BANNED_MODULES:
                issues.append(f"{path}:{node.lineno} banned import from '{module}'")
    return issues


def check_prints(tree: ast.Module, path: Path) -> list[str]:
    return [
        f"{path}:{node.lineno} print() call is forbidden in the domain layer"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]


def check_mutable_defaults(tree: ast.Module, path: Path) -> list[str]:
    issues: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        defaults = (*node.args.defaults, *node.args.kw_defaults)
        for default in defaults:
            if default is None:
                continue
            kind = MUTABLE_LITERALS.get(type(default))
            if kind is not None:
                issues.append(
                    f"{path}:{node.lineno} mutable default argument ({kind}) "
                    f"in function '{node.name}'"
                )
    return issues


def check_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        *check_imports(tree, path),
        *check_prints(tree, path),
        *check_mutable_defaults(tree, path),
    ]


def main(argv: list[str]) -> int:
    domain_dir = Path(argv[1]) if len(argv) > 1 else Path("src/books_api/domain")
    files = sorted(domain_dir.glob("*.py"))
    issues: list[str] = [issue for file in files for issue in check_file(file)]
    for issue in issues:
        report(issue)
    if issues:
        sys.stderr.write(f"Domain purity: {len(issues)} violation(s) found\n")
        return 1
    report(f"Domain purity: OK ({len(files)} files checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

</details>

> **Примечания.**
> 1. Скрипт намеренно пишет отчёт через `sys.stdout.write` и ошибки через `sys.stderr.write`, а не через `print`: в `pyproject.toml` из Урока 01 `per-file-ignores` покрывают только `tools/**` и `scripts/**` в корне, а путь скилла `.opencode/skills/...` под них не попадает.
> 2. Если строгий `ruff` (правило `INP001` для «не-пакетного» каталога) всё же заденет файлы скилла, добавьте в `per-file-ignores` строку `".opencode/skills/**/*.py" = ["INP001"]` — `noqa`-комментарии в коде скиллов остаются под запретом.
> 3. Хук плагина, который будет вызывать этот скрипт автоматически при каждом редактировании домена, появится в **Уроке 10** (`ctx.tool.hook` в `.opencode/plugins/*.ts`) — пока запускаем его руками или через промпт агенту.

### Шаг 4. Испытание 1: явная загрузка скилла по ID

Скилл можно подтолкнуть явно — упомянуть его ID в промпте. Отправьте в чат:

```text
Используй скилл domain-invariants: проверь все текущие сущности и Value Objects домена и закрой найденные щели в инвариантах и параметризованных тестах.
```

В транскрипте вы увидите вызов тула `skill` с `id: "domain-invariants"`, затем — тело SKILL.md, затем чтение `references/ddd-checklist.md` и запуск `scripts/check_purity.py` (потому что скилл это предписывает). Агент пройдёт чеклист по каждому VO/Entity `books-api`: например, убедится, что `Book.authors` — это `tuple[Author, ...]`, а не мутабельный список; что строки нормализуются `.strip()` и `"   "` отвергается `DomainError`; что `size_bytes <= 0` и отрицательная квота покрыты `@pytest.mark.parametrize`-граничными тестами; и завершит отчётом-таблицей «Модуль | Проверенный инвариант | Статус» после `just check` и `just test`.

### Шаг 5. Испытание 2: автозагрузка скилла без упоминания имени

Теперь проверим ленивую «рекламу». Откройте **новую чистую сессию** (`/new`) и отправьте обычный человеческий вопрос — ни слова о скиллах:

```text
Слушай, а нельзя ли случайно сломать внутреннее состояние Book или Reader, передав строки из пробелов или изменив список авторов снаружи после создания книги? Проверь наши бизнес-правила.
```

Посмотрите в транскрипт: OpenCode перед запросом показывает модели список доступных скиллов (ID + name + description — не тела!), и описание `Domain Invariants` совпадает с задачей. Агент **сам** вызовет тул `skill` с `id: "domain-invariants"` и только после этого начнёт аудит по чеклисту. Это и есть главное отличие скиллов от команд: вы не вспоминаете, что «у нас есть чеклист» — его вспоминает агент.

### Шаг 6. Зафиксируйте этап

```text
/commit
```

---

## Самопроверка

Выполните в терминале (или через `!`-команду / второй терминал):

```bash
find .opencode/skills/domain-invariants -type f | sort
python3 .opencode/skills/domain-invariants/scripts/check_purity.py
just check
just test
```

Чеклист результата:

- [ ] В `.opencode/skills/domain-invariants/` лежат `SKILL.md`, `references/ddd-checklist.md` и `scripts/check_purity.py`, и `SKILL.md` имеет frontmatter с `name` и содержательным `description` на русском.
- [ ] В чистой сессии запрос «по бизнес-правилам» без упоминания скилла привёл к видимому в транскрипте вызову тула `skill` с `id: "domain-invariants"`.
- [ ] `python3 .opencode/skills/domain-invariants/scripts/check_purity.py` печатает `Domain purity: OK (N files checked)` и завершается с кодом `0` (или все найденные нарушения устранены в домене).
- [ ] Коллекции внутри агрегатов возвращаются как `tuple`/`frozenset`, а граничные случаи строк и чисел покрыты `@pytest.mark.parametrize`-тестами для каждого подкласса `DomainError`.
- [ ] `just check` и `just test` зелёные; этап зафиксирован коммитом.

---

## Шпаргалка урока

| Команда / Файл | Назначение |
|---|---|
| `.opencode/skills/<id>/SKILL.md` | Каталожный скилл (рекомендуемая форма; даёт приватную базовую директорию для `references/` и `scripts/`) |
| `.opencode/skills/<name>.md` | Плоский однофайловый скилл (без выборки соседних файлов) |
| `description` в frontmatter | Единственное, что модель видит до загрузки скилла; без него скилл не рекламируется |
| `metadata.opencode/autoinvoke: false` / `disable-model-invocation: true` | Скрыть скилл из автосписка модели (явная загрузка по ID всё равно работает) |
| Тул `skill` с точным ID | Механизм ленивой загрузки тела скилла агентом |
| `@skill-id` в промпте | Явная загрузка скилла пользователем |
| `permissions` c `action: "skill"` | Правила `allow`/`ask`/`deny` на скилл-ID (последнее совпадение побеждает) |
| Массив `skills` в `opencode.jsonc` | Дополнительные локальные каталоги и HTTP-каталоги скиллов |
| `python3 scripts/check_purity.py` (из каталога скилла) | AST-аудит чистоты домена: запрещённые импорты, `print`, мутабельные дефолты |

Следующий шаг: **[Урок 07. Проектный MCP-сервер в `opencode.jsonc` и Code Mode (`execute`) →](07-mcp-servers-and-code-mode.md)**
