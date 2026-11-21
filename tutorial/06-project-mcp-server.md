# Урок 06. Проектный MCP-сервер в `.jcode/mcp.json`

[← Урок 05. Проектные скиллы](05-project-skills.md) | [Карта курса](README.md) | [Урок 07. Параллельная разработка со Swarm →](07-parallel-swarm.md)

## Цель урока

- Разобраться, как `jcode` подключает внешние инструменты по протоколу **MCP (Model Context Protocol)** на уровне конкретного репозитория (`.jcode/mcp.json` и `.mcp.json`).
- Научиться проверять и отлаживать MCP-серверы через CLI (`jcode mcp list` и `jcode mcp test <server>`) без траты токенов LLM.
- Поднять собственный компактный локальный `stdio` MCP-сервер на стандартной библиотеке Python (`tools/license_mcp.py`) со справочником лицензий Creative Commons / Public Domain и использовать его из чата `jcode` для реализации модуля `LicensePolicy`.

---

## Теория-минимум: проектные MCP-конфиги и режимы загрузки схем

MCP позволяет подключить к `jcode` любой внутренний источник правды вашей команды: корпоративный каталог API, локальную базу тестовых стендов, генератор схем или реестр лицензий.

### Приоритет файлов конфигурации в проекте

`jcode` объединяет глобальный `~/.jcode/mcp.json` с проектными файлами из корня рабочей директории в следующем порядке (более поздние переопределяют одноимённые серверы):

1. **`./.jcode/mcp.json`** (рекомендуемое место для проектных MCP-серверов `jcode`);
2. **`./.mcp.json`** (удобно, если конфиг разделяется с другими инструментами);
3. `./.claude/mcp.json` (если не отключено переменной `JCODE_DISABLE_CLAUDE_MCP`).

Поддерживаются как локальные процессы (`stdio`: поля `command`, `args`, `env`), так и удалённые серверы (`type: "http"` с `url`, `headers` и встроенным `jcode mcp login <server>` по OAuth). В строках конфигурации работает безопасная подстановка переменных окружения `${VAR}` и `${VAR:-default}`, поэтому секреты никогда не нужно хранить в Git.

### Почему MCP в `jcode` не тормозит старт и не бьёт по кэшу

- Сессия `jcode` стартует мгновенно (за миллисекунды), не дожидаясь сетевых рукопожатий MCP, и использует закэшированные схемы инструментов.
- По умолчанию работает умный режим `--mcp-tools auto` (`auto` / `eager` / `deferred`): если каталог MCP-инструментов большой, их схемы подгружаются отложенно через поиск `mcp(action="search")`, сохраняя статический префикс системного промпта и ваш prompt-кэш стабильными!

---

## Практика шаг за шагом

### Шаг 1. Напишите микро-сервер MCP справочника свободных лицензий

Чтобы не тянуть в наш чистый проект сторонние пакеты, напишем в `tools/license_mcp.py` самодостаточный `stdio` MCP-сервер на чистом Python 3.14 (полностью проходящий наш строгий контур `just check`: `ruff` + `ty`). Он отдаёт агенту официальные идентификаторы SPDX, правила атрибуции, `ShareAlike` и совместимости производных сборок для `books-api`.

Создайте файл `tools/license_mcp.py`:

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


def reply(req_id: int | str, result: dict[str, object]) -> None:
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}) + "\n")
    sys.stdout.flush()


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

### Шаг 2. Зарегистрируйте сервер в `.jcode/mcp.json` с подстановкой окружения

Создайте файл `.jcode/mcp.json`:

```json
{
  "mcpServers": {
    "books-licenses": {
      "command": "python3",
      "args": ["tools/license_mcp.py"],
      "env": {
        "BOOKS_LICENSE_POLICY": "${BOOKS_LICENSE_POLICY:-strict}"
      }
    }
  }
}
```

Обратите внимание на синтаксис `"${BOOKS_LICENSE_POLICY:-strict}"`: если переменная не задана в вашей оболочке, `jcode` автоматически подставит значение по умолчанию `strict`.

### Шаг 3. Протестируйте рукопожатие через `jcode mcp list` и `jcode mcp test`

Прежде чем идти в чат, проверим наш проектный MCP-сервер детерминированной CLI-командой во втором терминале:

```bash
jcode mcp list
jcode mcp test books-licenses
```

Ожидаемый вывод `jcode mcp test books-licenses`:

```text
Connected to MCP server 'books-licenses' and disconnected cleanly.
Server: books-license-catalog 0.1.0
Tools: 1
  inspect_free_license
```

Команда `mcp test` поднимает процесс, проходит протокол `initialize` + `tools/list`, печатает найденные инструменты и аккуратно завершает сервер, не вызывая LLM. Если в пути к скрипту опечатка, вы узнаете об этом за долю секунды!

### Шаг 4. Используйте проектный MCP-сервер внутри `jcode`

Если ваша TUI-сессия уже была открыта до создания `.jcode/mcp.json`, попросите агента перезагрузить MCP-конфигурацию (или просто начните задачу, упомянув сервер `books-licenses`):

```text
Перезагрузи MCP-серверы при необходимости и опроси наш проектный MCP-сервер `books-licenses` (инструмент `inspect_free_license`) для всех четырёх поддерживаемых лицензий (`PUBLIC_DOMAIN`, `CC0`, `CC_BY`, `CC_BY_SA`), а также проверь на нём несвободную лицензию `CC_BY_NC`.

На основе точных SPDX-идентификаторов и шаблонов `notice_template`, полученных от MCP-сервера, создай модуль `src/books_api/domain/license_policy.py`:
1. Функцию/сервис генерации обязательного лицензионного уведомления для книги `build_license_notice(book: Book) -> str` (подставляющую имена авторов книги в шаблон для лицензий с атрибуцией).
2. Функцию расчёта результирующей лицензии сборника книг `resolve_anthology_license(books: Sequence[Book]) -> LicenseType` (если в сборнике есть хотя бы одна книга `CC_BY_SA`, весь сборник обязан распространяться под `CC_BY_SA`, иначе если есть `CC_BY` -> `CC_BY`, иначе `CC0` / `PUBLIC_DOMAIN`; пустой список отвергать `DomainError`).
Добавь юнит-тесты в `tests/test_license_policy.py` и прогони `just check` и `just test`.
```

Посмотрите в TUI: агент вызовет инструмент `mcp` (`server="books-licenses"`, `tool="inspect_free_license"`), получит точные строки `spdx` и `notice_template` прямо из вашего локального сервера и перенесёт их в доменную логику и тесты без галлюцинаций!

Сделайте коммит этапа:

```text
/commit
```

---

## Самопроверка

Выполните в терминале:

```bash
jcode mcp test books-licenses
just check
just test
```

Чеклист результата:

- [ ] В `.jcode/mcp.json` подключён `books-licenses`, и `jcode mcp test books-licenses` проходит успешно.
- [ ] Создан `src/books_api/domain/license_policy.py` с генерацией текста лицензии и расчётом лицензии антологии (`ShareAlike` доминирует над `CC_BY`, а `CC_BY` над `CC0`/`PUBLIC_DOMAIN`).
- [ ] Весь код (включая `tools/license_mcp.py`) чисто проходит `just check` и `just test`.

---

## Шпаргалка урока

| Файл / Команда | Назначение |
|---|---|
| `./.jcode/mcp.json` (или `./.mcp.json`) | Проектный список локальных (`stdio`) и удалённых (`http`/`sse`) MCP-серверов |
| `${VAR:-default}` | Подстановка переменных окружения в `url`, `headers` и `env` внутри `mcp.json` |
| `jcode mcp list` | Показать все сконфигурированные глобальные и проектные MCP-серверы |
| `jcode mcp test <server>` | Проверить запуск, рукопожатие и список тулов MCP-сервера без вызова модели |
| `jcode mcp login <server>` | Пройти интерактивный OAuth-вход для удалённого HTTP MCP-сервера |

Следующий шаг: **[Урок 07. Параллельная разработка со Swarm →](07-parallel-swarm.md)**
