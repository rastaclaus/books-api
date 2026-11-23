# Урок 07. Проектный MCP-сервер в `opencode.jsonc` и Code Mode (`execute`)

[← Урок 06. Проектные скиллы](06-project-skills-and-bundled-resources.md) | [Карта курса](README.md) | [Урок 08. Кастомные агенты, permissions/policies и независимое ревью →](08-custom-agents-permissions-and-subagent-review.md)

## Цель урока

- Настроить проектный MCP-сервер (Model Context Protocol) строго под ключом **`mcp.servers`** в `opencode.jsonc` (в V2 имена серверов НЕ кладутся плоским списком под `mcp`), с подстановкой окружения `{env:NAME}`.
- Освоить CLI-управление серверами: `opencode mcp add` / `opencode mcp list`, статусы `connected` / `needs authentication` и панель `/mcps` в TUI для OAuth.
- Понять **Code Mode** — режим по умолчанию в V2, при котором MCP-тулы не вываливаются в нативный список тулов провайдера, а агент дотягивается до них через тул `execute`, сочиняя компактный JavaScript-код.
- Поднять собственный локальный `stdio` MCP-сервер справочника лицензий на чистом Python 3.14 и использовать его как «источник правды» для доменного модуля `LicensePolicy` — без галлюцинаций SPDX-идентификаторов.

---

## Теория-минимум: `mcp.servers`, именование тулов и Code Mode

### Конфигурация: только `mcp.servers`

Серверам нужны уникальные имена под ключом `mcp.servers`. V2 **не** помещает имена серверов непосредственно под `mcp`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "my-server": {
        "type": "local",
        "command": ["npx", "-y", "example-mcp-server"],
      },
    },
  },
}
```

**Локальный сервер** — это процесс, который OpenCode запускает по stdio-транспорту:

```jsonc
{
  "mcp": {
    "servers": {
      "books-licenses": {
        "type": "local",
        "command": ["python3", "tools/license_mcp.py"],
        "cwd": ".",
        "environment": {
          "BOOKS_LICENSE_POLICY": "{env:BOOKS_LICENSE_POLICY:-strict}",
        },
      },
    },
  },
}
```

| Поле | Обязательно | Описание |
|---|---|---|
| `type` | Да | Должно быть `"local"` |
| `command` | Да | Исполняемый файл и его аргументы (массив строк) |
| `cwd` | Нет | Рабочая директория процесса; относительные пути резолвятся от workspace (значение по умолчанию) |
| `environment` | Нет | Строковые переменные, добавляемые к унаследованному окружению процесса OpenCode |
| `disabled` | Нет | `true` — сервер сконфигурирован, но не подключается (по умолчанию `false`) |
| `codemode` | Нет | `false` — отдавать тулы напрямую вместо Code Mode (по умолчанию `true`) |
| `timeout` | Нет | Перекрытия таймаутов для конкретного сервера |

**Важно про подстановку окружения.** В `environment` работает подстановка `{env:NAME}`. Shell-выражения вроде `$NAME` в JSON-строках **не раскрываются**. В отличие от синтаксиса `${VAR:-default}` в отдельных конфиг-файлах других инструментов, здесь значение по умолчанию внутри строки `{env:...}` не берётся — надёжнее всего прочитать переменную в самом скрипте через `os.environ.get("BOOKS_LICENSE_POLICY", "strict")` и хранить в конфиге ссылку `{env:BOOKS_LICENSE_POLICY:-strict}` только как документацию намерения (или вообще опустить `environment`, если скрипт сам деградирует к умолчанию).

**Удалённый сервер** использует MCP Streamable HTTP-транспорт и требует абсолютный URL:

```jsonc
{
  "mcp": {
    "servers": {
      "context7": {
        "type": "remote",
        "url": "https://mcp.context7.com/mcp",
        "oauth": false,
        "headers": {
          "CONTEXT7_API_KEY": "{env:CONTEXT7_API_KEY}",
        },
      },
    },
  },
}
```

`oauth: false` ставят только если сервер использует API-ключ или иной заголовочный credential вместо OAuth. Секреты храним в переменных окружения (`{env:NAME}`), а не в файле: файл коммитится в Git.

### CLI: `opencode mcp add` и `opencode mcp list`

Сервер можно добавить командой, которая допишет его в проектный конфиг:

```bash
opencode mcp add books-licenses -- python3 tools/license_mcp.py
# переменные окружения — через повторяемые флаги --env:
opencode mcp add books-licenses --env BOOKS_LICENSE_POLICY=strict -- python3 tools/license_mcp.py
# удалённый:
opencode mcp add context7 --url https://mcp.context7.com/mcp
```

Проверка состояния серверов из второго терминала:

```bash
opencode mcp list
```

Возможные статусы: `✓ books-licenses  connected` (сервер готов к использованию агентом) или `needs authentication` — тогда в OpenCode выполняем `/mcps`, выбираем сервер и проходим вход (для локального stdio-сервера аутентификация не нужна). Серверы подключаются автоматически; чтобы держать сервер в конфиге без подключения, используется поле `disabled`, а не `enabled`.

### Именование тулов, промптов и ресурсов

OpenCode называет тул по шаблону `<server>_<tool>`, заменяя символы, отличные от букв, цифр, `_` и `-`, на `_`:

```text
server: context 7
tool:   resolve.library/id
name:   context_7_resolve_library_id
```

MCP-промпты становятся командами с тем же правилом нормализации: `/<server>:<prompt>` (например, `/context_7:find_docs react "server components"` — аргументы подставляются по порядку через пробел, значения с пробелами в кавычках). Ресурсы MCP агент читает через два встроенных тула: `list_mcp_resources` и `read_mcp_resource` (их права настраиваются действиями `opencode_list_mcp_resources` и `opencode_read_mcp_resource`).

### Code Mode: тулы через `execute`, а не в нативный список

По умолчанию в V2 `codemode: true` (это же — значение по умолчанию поля `codemode` каждого сервера). Это значит:

- схемы MCP-тулов **не** добавляются в нативный список тулов провайдера — контекст модели остаётся компактным;
- агент достаётся до тулов через встроенный тул **`execute`**: внутри него выполняется JavaScript, где тулы сгруппированы по нормализованному имени сервера:

```javascript
const result = await tools.books_licenses.inspect_free_license({ code: "CC_BY_SA" });
```

- полный каталог доступных тулов агент находит через функцию `search(...)` внутри того же `execute`;
- независимые вызовы можно объединять в один шаг `execute` и запускать параллельно через `Promise.allSettled` — вместо последовательной череды отдельных tool-call'ов.

Если какой-то сервер несовместим с Code Mode, у конкретного сервера ставится `codemode: false` — его тулы вернутся в нативный список провайдера.

### Permissions для MCP-тулов

Разрешения настраиваются действием `<server>_<tool>` (с нормализацией символов в `_`) и ресурсом `*`:

```jsonc
{
  "permissions": [
    { "action": "books_licenses_inspect_free_license", "resource": "*", "effect": "allow" },
  ],
}
```

Отдельное действие `execute` управляет самим Code Mode: `deny` на `execute` убирает Code Mode и раскрывает тулы напрямую (вложенные тулы при этом всё равно проходят свои проверки).

---

## Практика шаг за шагом

### Шаг 1. Напишите локальный stdio MCP-сервер справочника лицензий

Чтобы не тянуть в наш чистый проект сторонние пакеты, напишем `tools/license_mcp.py` — самодостаточный `stdio` MCP-сервер на чистом Python 3.14 (JSON-RPC по строкам stdin/stdout, методы `initialize` / `tools/list` / `tools/call`), полностью проходящий наш строгий контур `just check`:

```text
Создай файл tools/license_mcp.py — самодостаточный stdio MCP-сервер на чистом Python 3.14 (только stdlib, полная типизация, проходит ruff select=ALL и ty check без замечаний и без noqa).

Требования:
1. JSON-RPC 2.0 по строкам stdin/stdout: обрабатывай методы "initialize", "tools/list", "tools/call" (и возвращай пустой result на остальное). Ответ — одна строка JSON + \n, с flush.
2. Один тул inspect_free_license с аргументом code (строка, обязательный).
3. Справочник LICENSES для четырёх лицензий свободной раздачи:
   - PUBLIC_DOMAIN: spdx CC-PDDC, атрибуция не нужна, ShareAlike нет, коммерческое использование разрешено;
   - CC0: spdx CC0-1.0, атрибуция не нужна;
   - CC_BY: spdx CC-BY-4.0, атрибуция нужна, ShareAlike нет;
   - CC_BY_SA: spdx CC-BY-SA-4.0, атрибуция нужна, ShareAlike да.
   У каждой записи поля: spdx (str), requires_attribution (bool), share_alike (bool), allows_commercial (bool), can_bundle_with (list[str] из всех четырёх кодов), notice_template (str — шаблон с подстановкой {authors}).
4. Неизвестный код (например CC_BY_NC) → allowed_in_catalog: false и reason про запрет несвободных лицензий в books-api.
5. STRICT_MODE = os.environ.get("BOOKS_LICENSE_POLICY", "strict") — значение по умолчанию берём в самом скрипте (shell-подстановки в JSON-строках конфига не работают). Включай policy_mode в каждый ответ.
6. В ответе initialize: serverInfo {"name": "books-license-catalog", "version": "0.1.0"}.
7. Вывод не через print, а через аккуратные функции записи в sys.stdout (чтобы код был чистым и для ruff T201), shebang #!/usr/bin/env python3 и chmod +x.
```

<details>
<summary>Эталонный ориентир <code>tools/license_mcp.py</code> (нажмите, чтобы сверить)</summary>

```python
#!/usr/bin/env python3
"""Локальный stdio MCP-сервер справочника свободных лицензий для books-api."""

import json
import os
import sys
from typing import TypedDict


class LicenseInfo(TypedDict):
    spdx: str
    requires_attribution: bool
    share_alike: bool
    allows_commercial: bool
    can_bundle_with: list[str]
    notice_template: str


STRICT_MODE = os.environ.get("BOOKS_LICENSE_POLICY", "strict")

LICENSES: dict[str, LicenseInfo] = {
    "PUBLIC_DOMAIN": {
        "spdx": "CC-PDDC",
        "requires_attribution": False,
        "share_alike": False,
        "allows_commercial": True,
        "can_bundle_with": ["PUBLIC_DOMAIN", "CC0", "CC_BY", "CC_BY_SA"],
        "notice_template": "This work is in the public domain.",
    },
    "CC0": {
        "spdx": "CC0-1.0",
        "requires_attribution": False,
        "share_alike": False,
        "allows_commercial": True,
        "can_bundle_with": ["PUBLIC_DOMAIN", "CC0", "CC_BY", "CC_BY_SA"],
        "notice_template": "Dedicated to the public domain under CC0 1.0 Universal.",
    },
    "CC_BY": {
        "spdx": "CC-BY-4.0",
        "requires_attribution": True,
        "share_alike": False,
        "allows_commercial": True,
        "can_bundle_with": ["PUBLIC_DOMAIN", "CC0", "CC_BY", "CC_BY_SA"],
        "notice_template": "Licensed under CC BY 4.0. Attribution to {authors} is required.",
    },
    "CC_BY_SA": {
        "spdx": "CC-BY-SA-4.0",
        "requires_attribution": True,
        "share_alike": True,
        "allows_commercial": True,
        "can_bundle_with": ["PUBLIC_DOMAIN", "CC0", "CC_BY", "CC_BY_SA"],
        "notice_template": "Licensed under CC BY-SA 4.0. Attribution to {authors} and ShareAlike required.",
    },
}

TOOLS = [
    {
        "name": "inspect_free_license",
        "description": "Return SPDX code, notice template, and bundling rules for a books-api license.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "License code (PUBLIC_DOMAIN, CC0, CC_BY, CC_BY_SA, or any candidate code).",
                }
            },
            "required": ["code"],
        },
    }
]


def write_line(text: str) -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def reply(req_id: int | str, result: dict[str, object]) -> None:
    write_line(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}))


def main() -> None:
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        msg: object = json.loads(line)
        if not isinstance(msg, dict):
            continue
        req_id = msg.get("id")
        method = msg.get("method")
        if not isinstance(req_id, (int, str)):
            continue
        if method == "initialize":
            reply(
                req_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "books-license-catalog", "version": "0.1.0"},
                },
            )
        elif method == "tools/list":
            reply(req_id, {"tools": TOOLS})
        elif method == "tools/call":
            params = msg.get("params")
            args = params.get("arguments") if isinstance(params, dict) else None
            raw_code = args.get("code", "") if isinstance(args, dict) else ""
            code = str(raw_code).strip().upper()
            info = LICENSES.get(code)
            payload: dict[str, object] = (
                {"allowed_in_catalog": True, "policy_mode": STRICT_MODE, "code": code, **info}
                if info is not None
                else {
                    "allowed_in_catalog": False,
                    "policy_mode": STRICT_MODE,
                    "code": code,
                    "reason": "Non-free license (e.g. NC/ND or proprietary) is forbidden in books-api.",
                }
            )
            reply(req_id, {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]})
        else:
            reply(req_id, {})


if __name__ == "__main__":
    main()
```

</details>

Сделайте скрипт исполняемым и проверьте рукопожатие вручную — это подскажет проблемы раньше OpenCode:

```bash
chmod +x tools/license_mcp.py
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | python3 tools/license_mcp.py
```

### Шаг 2. Зарегистрируйте сервер в `opencode.jsonc` под `mcp.servers`

Попросите агента дополнить проектный конфиг:

```text
Зарегистрируй в opencode.jsonc проектный MCP-сервер: строго под ключом mcp.servers (не плоско под mcp!) добавь сервер с именем books-licenses:
{
  "type": "local",
  "command": ["python3", "tools/license_mcp.py"],
  "cwd": ".",
  "environment": { "BOOKS_LICENSE_POLICY": "{env:BOOKS_LICENSE_POLICY:-strict}" }
}
```

Получившийся фрагмент `opencode.jsonc`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "books-licenses": {
        "type": "local",
        "command": ["python3", "tools/license_mcp.py"],
        "cwd": ".",
        "environment": {
          "BOOKS_LICENSE_POLICY": "{env:BOOKS_LICENSE_POLICY:-strict}",
        },
      },
    },
  },
}
```

Обратите внимание на `{env:BOOKS_LICENSE_POLICY:-strict}`: если переменная не задана в вашей оболочке, в `environment` сервера попадёт пустая строка — но на поведение это не повлияет, потому что значение по умолчанию сервер берёт сам через `os.environ.get("BOOKS_LICENSE_POLICY", "strict")` в скрипте. Такой «двойной ремень» — это нормально: подстановка `{env:...}` передаёт явно заданное значение, а дефолт живёт в коде.

### Шаг 3. Проверьте подключение из второго терминала

```bash
opencode mcp list
```

Ожидаемый вывод:

```text
✓ books-licenses  connected
```

Сервер подключается автоматически; для локального stdio-сервера OAuth не требуется. В TUI список серверов и их состояние всегда доступен через панель `/mcps` (leader `Ctrl+X`, затем `M` занято `/models` — используйте палитру `Ctrl+P` или введите `/mcps` в строке промпта). Если статус `needs authentication` — в `/mcps` выбрать сервер и пройти вход (актуально только для `remote`-серверов с OAuth).

### Шаг 4. Используйте сервер в чате и наблюдайте Code Mode

Отправьте в чат боевую задачу:

```text
Опроси наш проектный MCP-сервер books-licenses (тул inspect_free_license) для всех четырёх поддерживаемых лицензий (PUBLIC_DOMAIN, CC0, CC_BY, CC_BY_SA) и проверь несвободную CC_BY_NC.

На основе точных SPDX-идентификаторов и шаблонов notice_template создай модуль src/books_api/domain/license_policy.py:
1. Функцию build_license_notice(book: Book) -> str — подставляет имена авторов книги в шаблон для лицензий с атрибуцией (для лицензий без атрибуции — базовый текст уведомления).
2. Функцию resolve_anthology_license(books: Sequence[Book]) -> LicenseType — ShareAlike доминирует над CC_BY, CC_BY над CC0/PUBLIC_DOMAIN; пустой список отвергать DomainError.
Добавь юнит-тесты в tests/test_license_policy.py и прогони just check и just test.
```

Следите за транскриптом: из-за Code Mode по умолчанию (`codemode: true`) тулы `books-licenses_inspect_free_license` **не появятся** в нативном списке тулов модели — вместо этого агент один раз вызовет тул `execute` и внутри него напишет компактный JavaScript вида:

```javascript
const [pd, cc0, by, bysa, nc] = await Promise.allSettled([
  await tools.books_licenses.inspect_free_license({ code: "PUBLIC_DOMAIN" }),
  await tools.books_licenses.inspect_free_license({ code: "CC0" }),
  await tools.books_licenses.inspect_free_license({ code: "CC_BY" }),
  await tools.books_licenses.inspect_free_license({ code: "CC_BY_SA" }),
  await tools.books_licenses.inspect_free_license({ code: "CC_BY_NC" }),
]);
return { pd, cc0, by, bysa, nc };
```

— все пять опросов одним шагом, параллельно. Если агент не помнит точную сигнатуру, он сначала найдёт тул функцией `search(...)` внутри того же `execute` — обратите на это внимание при чтении транскрипта.

Агент перенесёт полученные с сервера точные строки `spdx` (CC-PDDC, CC0-1.0, CC-BY-4.0, CC-BY-SA-4.0) и `notice_template` в доменную логику и тесты без галлюцинаций: `build_license_notice` подставит имена авторов в шаблон для `CC_BY`/`CC_BY_SA`, а `resolve_anthology_license` реализует доминирование `CC_BY_SA > CC_BY > CC0 > PUBLIC_DOMAIN` с `DomainError` на пустом списке.

### Шаг 5. Зафиксируйте этап

```text
/commit
```

---

## Самопроверка

Выполните в терминале (или через `!`-команду / второй терминал):

```bash
opencode mcp list | grep books-licenses
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 tools/license_mcp.py
just check
just test
```

Чеклист результата:

- [ ] `opencode mcp list` показывает `books-licenses connected`, а сервер зарегистрирован строго под `mcp.servers` в `opencode.jsonc`.
- [ ] В транскрипте чата виден вызов тула `execute` с кодом `await tools.books_licenses.inspect_free_license({...})` — MCP-тулы не попали в нативный список тулов (Code Mode по умолчанию).
- [ ] Создан `src/books_api/domain/license_policy.py` с `build_license_notice` и `resolve_anthology_license` (`ShareAlike` доминирует над `CC_BY`, `CC_BY` над `CC0`/`PUBLIC_DOMAIN`, пустой список — `DomainError`), SPDX-идентификаторы взяты с MCP-сервера, а не придуманы.
- [ ] Весь код (включая `tools/license_mcp.py`) чисто проходит `just check`, и `just test` зелёный; этап зафиксирован коммитом.

---

## Шпаргалка урока

| Команда / Файл | Назначение |
|---|---|
| `mcp.servers` в `opencode.jsonc` | Единственное место конфигурации MCP-серверов в V2 (имена серверов под вложенным ключом, не плоско под `mcp`) |
| `{env:NAME}` / `environment` | Подстановка переменных окружения в конфиге; shell-выражения `$NAME` не раскрываются, дефолт надёжнее брать в скрипте через `os.environ.get` |
| `opencode mcp add <name> -- python3 ...` | Добавить локальный сервер в проектный конфиг (`--env` — переменные, `--global` — в глобальный конфиг) |
| `opencode mcp list` | Статусы серверов: `connected` / `needs authentication` |
| `/mcps` в TUI | Просмотр, подключение/отключение и OAuth-вход для серверов |
| `<server>_<tool>` | Нормализованное имя тула (недопустимые символы → `_`); MCP-промпты становятся командами `/<server>:<prompt>` |
| Code Mode (`codemode: true` по умолчанию) | Тулы не в нативном списке провайдера; агент вызывает их через тул `execute` (`await tools.<server>_<tool>({...})`, группы по имени сервера, поиск каталога через `search(...)`) |
| `codemode: false` у сервера | Вернуть тулы сервера в нативный список (при несовместимости с Code Mode) |
| `permissions` с `action: "<server>_<tool>"` | Правила `allow`/`ask`/`deny` для MCP-тулов; `deny` на `execute` отключает Code Mode |
| `list_mcp_resources` / `read_mcp_resource` | Чтение MCP-ресурсов агентом (`opencode_list_mcp_resources` / `opencode_read_mcp_resource` — их permission-действия) |
| `tools/license_mcp.py` | Наш локальный stdio-сервер справочника свободных лицензий (источник правды для `LicensePolicy`) |

Следующий шаг: **[Урок 08. Кастомные агенты, permissions/policies и независимое ревью →](08-custom-agents-permissions-and-subagent-review.md)**
