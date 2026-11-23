# Урок 02. Конфигурация `opencode.jsonc` vs `cli.json`, варианты моделей, форматтеры и warming

[← Урок 01. Рабочее пространство, TUI и `AGENTS.md`](01-workspace-tui-and-agents-md.md) | [Карта курса](README.md) | [Урок 03. Plan-режим, steering, снапшоты и `/diff` →](03-plan-mode-steering-snapshots-and-diff.md)

## Цель урока

- Разобраться в двух уровнях настроек OpenCode V2: серверно-проектный `opencode.jsonc` (в корне репозитория или в `.opencode/`) и терминальный `~/.config/opencode/cli.json` — понять, что к какому файлу относится и почему их нельзя смешивать.
- Освоить иерархию слияния конфигов (глобальный → корневой → `.opencode/`), горячую перезагрузку конфигов (`opencode reload`, команда `location.reload`), подстановки `{env:VAR}` и `{file:path}`, выбор модели и вариантов (`/models`, `provider/model#variant`, `Ctrl+T`, `F2`).
- Включить встроенные форматтеры (`formatter: true` — для `.py` это `ruff`), обсудить, почему для `books-api` тайпчекер лучше гонять CLI-командой `ty check` через `just check`, а не держать постоянный фоновый LSP, кратко познакомиться с `warming` и контролем расходов (`opencode stats`, `debug.turn_tokens`).
- Закрепить это на деле: настроить проектный конфиг, добавить гайд доменного стиля через массив `instructions` и создать Value Objects домена `books-api`: `BookFormat`, `LanguageCode`, `ISBN`, `LicenseType`.

---

## Теория-минимум: два конфига, которые легко перепутать

В OpenCode V2 настройки строго разделены по назначению:

| Файл | Назначение | Кто читает |
|---|---|---|
| `~/.config/opencode/opencode.jsonc` | Глобальные пользовательские настройки **сервера** (для всех проектов) | Фоновый сервер |
| `./opencode.jsonc` (корень) и `./.opencode/opencode.jsonc` | Настройки **проекта**: `model`, `permissions`, `policies`, `mcp`, `formatter`, `instructions`, `references`, `warming`, агенты, скиллы, плагины | Фоновый сервер |
| `~/.config/opencode/cli.json` | Настройки **только терминального клиента**: тема, keybinds, вкладки, диффы, `debug.turn_tokens` | TUI / `opencode mini` |

Важные детали:

1. **Схемы разные.** В `opencode.jsonc` пишем `"$schema": "https://opencode.ai/config.json"`, а в `cli.json` — `"$schema": "https://opencode.ai/v2/cli.json"`. Благодаря `$schema` редактор подскажет поля и подсветит опечатки. Проектного `cli.json` не существует — терминальные настройки глобальные.
2. **Иерархия слияния (от низшего к высшему):** глобальный `~/.config/opencode/opencode.jsonc` → корневые `opencode.jsonc` от дальних директорий к ближним → файлы в `.opencode/` директориях в том же порядке. Каждый обнаруженный конфиг в `.opencode/` перекрывает все корневые. Непересекающиеся настройки сохраняются все.
3. **Горячая перезагрузка.** Изменения конфигов подхватываются без перезапуска сервера: работающие сессии продолжают работу с обновлёнными настройками на следующей границе шага. Есть и явная команда `opencode reload` (перезагружает конфигурацию без рестарта сервера). В TUI изменения конфигов отслеживаются автоматически; в `cli.json` валидные правки перезагружаются прямо во время работы TUI.
4. **Подстановки.** В строковых значениях конфига работают `{env:VARIABLE}` (переменная окружения; если не задана — пустая строка) и `{file:path}` (содержимое файла; путь относительный от конфига, абсолютный или с `~/`; если файла нет — пустая строка). Удобно для секретов: `{file:~/.secrets/api-key}`.
5. **Модели и варианты.** `/models` (или `Ctrl+X`, затем `M`) выбирает модель для текущей сессии — конфиг при этом не переписывается. Полная запись — `provider/model#variant`: варианты — именованные настройки одной модели (уровень «усилий» рассуждений и т.п.). Хоткей `variant.cycle` (`Ctrl+T`) переключает варианты модели, `F2` — цикл по недавним моделям (`Shift+F2` — в обратную сторону). Учтите: в корневой настройке `model` варианта сейчас не сохраняется — `#variant` доступен в ссылках на модель у агентов и команд и в `--model`.
6. **Форматтеры.** `"formatter": true` включает все встроенные форматтеры: после `write`, `edit` или `patch` файл форматируется автоматически. Для Python это `ruff` (требует команду `ruff` и конфиг ruff/зависимость в проекте) или `uv`. Отдельный форматтер отключается записью `{"formatter": {"prettier": {"disabled": true}}}`, а кастомный задаётся массивом `command` (не строкой!) и `extensions`, где `$FILE` заменяется на абсолютный путь файла.
7. **А что же тайпчекер?** Встроенные форматтеры OpenCode — это именно *форматирование* файлов после правок. Тайпчек (`ty check`) не встраивается в этот конвейер, и постоянный фоновый LSP для него избыточен: в нашем контуре `ty` — это строгие ворота качества, которые нужно пробегать явно и целиком, поэтому мы вызываем `ty check` через рецепт `just check` (агент делает это перед сдачей задачи по контракту из `AGENTS.md`). Одна консистентная CLI-команда — предсказуемее и быстрее, чем дублирование LSP и CLI с потенциально разными настройками.
8. **Warming.** `"warming": true` удерживает prompt-кэш провайдера: пока вы паузите между запросами, OpenCode отправляет периодические transient-запросы «just before cache expires» — на 90% `cache.ttl` модели (или раз в 4 минуты без него), до 30 минут с последнего обычного запроса. Включается осознанно: warming-запросы — реальные платные запросы.
9. **Контроль расходов.** `opencode stats --project . --cost --models` покажет затраты по текущему проекту, с разбивкой по моделям. А `"debug": {"turn_tokens": true}` в `cli.json` выводит per-turn расход токенов прямо в TUI (`"verbose"` добавит ещё и входы тулов).

---

## Практика шаг за шагом

### Шаг 1. Создайте проектный `opencode.jsonc`

Попросите агента создать проектный конфиг с включённым форматтером и дополнительным файлом инструкций:

```text
Создай в корне проекта файл opencode.jsonc с полями:
1. "$schema": "https://opencode.ai/config.json" — для валидации в редакторе.
2. "formatter": true — чтобы после каждого write/edit/patch OpenCode автоматически форматировал .py файлы встроенным ruff-форматтером (команда ruff у нас есть в dev-зависимостях и конфиг в pyproject.toml уже настроен).
3. "instructions": ["docs/guidelines/domain-style.md"] — файл с правилами доменного стиля, который мы создадим следующим шагом.
Ничего лишнего в конфиг не добавляй.
```

Затем создайте второй файл — гайд доменного стиля, который дополнит `AGENTS.md` детальными правилами моделирования:

```text
Создай файл docs/guidelines/domain-style.md с правилами моделирования домена books-api (чистый Domain Layer на Python 3.14). Зафиксируй там:
1. Все Value Objects — @dataclass(frozen=True, slots=True).
2. Валидация инвариантов выполняется в __post_init__; за нарушение выбрасываются исключения, унаследованные от DomainError (ValidationError и специализированные наследники).
3. Нормализация значений (обрезка/регистр строк) — только через object.__setattr__ внутри __post_init__, это единственный способ «мягкой» нормализации во frozen-датаклассе.
4. Магические пороги и лимиты — именованные константы модуля, никаких «волшебных чисел» в коде.
5. Никаких фабрик ради фабрик: если объект создаётся конструктором без драматических сложностей, не оборачивай его в фабричные методы/классы.
Файл должен быть компактным (не более ~40 строк) и написанным как инструкция для агента, а не как учебный текст.
```

Сравните с корневым `AGENTS.md`: там — архитектурные границы и ворота качества, а в `docs/guidelines/domain-style.md` — тонкие правила стиля моделирования. Оба файла теперь загружаются в каждую сессию этого проекта.

### Шаг 2. Проверьте итоговую слитую конфигурацию

Во втором терминале выполните:

```bash
opencode debug config | grep -B2 -A8 -e formatter -e instructions
```

Вы должны увидеть `"formatter": true` и ваш путь `docs/guidelines/domain-style.md` в `instructions` — это доказывает, что корневой `opencode.jsonc` подхвачен сервером и слит с глобальным конфигом. Если в правку конфига делались изменения прямо во время сессии — OpenCode перечитает их автоматически; можно и явно: `opencode reload` (или в TUI через палитру `Ctrl+P` — `location.reload`).

### Шаг 3. Включите per-turn токены через `OPENCODE_CLI_CONFIG_CONTENT`

Настройка `debug.turn_tokens` относится к **терминальному клиенту**, поэтому живёт в `cli.json`, а не в `opencode.jsonc`. Чтобы не трогать файл, передайте inline-конфиг через переменную окружения:

```bash
OPENCODE_CLI_CONFIG_CONTENT='{"$schema":"https://opencode.ai/v2/cli.json","debug":{"turn_tokens":true}}' opencode
```

Inline-настройки сливаются поверх глобального `cli.json` (вложенные объекты объединяются), и пока переменная задана — остаются приоритетными. Запустите TUI с этой переменной, отправьте любой промпт и найдите в футере транскрипта per-turn расход токенов: так вы будете видеть «цену» каждого хода агента. Позже можно перенести `"debug": {"turn_tokens": true}` в постоянный `~/.config/opencode/cli.json`.

> Заметьте иерархию ещё раз: `"formatter"` и `"instructions"` — в проектном `opencode.jsonc` (сервер видит их во всех клиентах), `"debug.turn_tokens"` — в `cli.json` (только TUI).

### Шаг 4. Осмотритесь с моделями и вариантами

В TUI:

- `Ctrl+X`, затем `M` (или `/models`) — откройте каталог моделей: только включённые модели с доступным провайдером в этом проекте. Выбор действует для текущей сессии и не меняет конфиг.
- `F2` — переключение по недавним моделям; `Shift+F2` — в обратную сторону.
- `Ctrl+T` (`variant.cycle`) — цикл по вариантам текущей модели, если у неё есть варианты (например, уровни reasoning-усилий). Если у модели вариантов нет — хоткей ничего не предложит.

Полная запись `provider/model#variant` пригодится в конфиге агентов и в `opencode run --model ...` — это мы используем в Уроке 08.

### Шаг 5. Реализуйте Value Objects домена

Теперь боевая задача. Отправьте в чат:

```text
Реализуй Value Objects домена books-api в новом модуле src/books_api/domain/value_objects.py, следуя AGENTS.md и docs/guidelines/domain-style.md (моделируем каталог свободной раздачи электронных книг).

1. BookFormat — StrEnum со значениями EPUB, PDF, MOBI.
2. LanguageCode — frozen Value Object двухбуквенного кода языка по ISO 639-1: в __post_init__ проверь формат ровно двух латинских букв, нормализуй в нижний регистр через object.__setattr__; нарушение формата выбрасывает ValidationError. Храни одно каноническое поле value: str.
3. ISBN — frozen Value Object, принимающий ISBN-10 или ISBN-13: в __post_init__ нормализуй к канонической строке без разделителей (убери дефисы и пробелы через object.__setattr__), проверь допустимые символы и валидность контрольной цифры (взвешенная сумма: для ISBN-10 — веса 10..1 с заменой X на 10 в контрольной позиции; для ISBN-13 — чередующиеся веса 1 и 3). Некорректный ISBN выбрасывает ValidationError. Храни value: str.
4. LicenseType — StrEnum со значениями PUBLIC_DOMAIN, CC0, CC_BY, CC_BY_SA. Добавь свойства:
   - requires_attribution -> bool: True для CC_BY и CC_BY_SA;
   - is_share_alike -> bool: True только для CC_BY_SA.
   Попытку создать несвободную лицензию из строки (например, LICENSE_TYPE из "proprietary", "commercial" или любой строки, не совпадающей с допустимыми значениями) обрабатывай как LicenseViolationError — реализуй клапс-метод LicenseType.from_string(value: str), который для неизвестного значения выбрасывает LicenseViolationError.
Все классы строго типизированы, сообщения ошибок — лаконичные. Экспортируй BookFormat, LanguageCode, ISBN, LicenseType в src/books_api/domain/__init__.py с обновлением __all__ (рядом с существующими ошибками).
Создай tests/test_value_objects.py с юнит-тестами: happy-path для каждого VO, нормализация регистра/разделителей, валидация контрольной цифры ISBN на корректном и некорректном примере, requires_attribution/is_share_alike для всех значений LicenseType, from_string для свободных и несвободных строк.
Перед завершением прогони just check и just test.
```

Пока агент работает, обратите внимание:

- Он сам прочитает `docs/guidelines/domain-style.md` (подключён через `instructions` в `opencode.jsonc`) и применит `@dataclass(frozen=True, slots=True)`, `__post_init__` и `object.__setattr__` без дополнительных напоминаний.
- После каждого `write`/`edit` OpenCode прогонит встроенный ruff-форматтер: в транскрипте у записей тулов появятся заметки о форматировании. Файлы придут уже выровненными под ваш `line-length = 120` из `pyproject.toml`.
- В футере TUI (если вы запустили Шаг 3 с `debug.turn_tokens`) видно расход токенов каждого хода.

### Шаг 6. Финальная проверка и фиксация прогресса

```bash
just check
just test
git status --short
opencode stats --project . --cost --models
```

Закоммитьте этап вручную (свою команду `/commit` мы создадим в Уроке 05):

```text
Проанализируй git status и git diff и создай осмысленный коммит в стиле Conventional Commits: opencode.jsonc, docs/guidelines/domain-style.md, src/books_api/domain/value_objects.py, обновлённый src/books_api/domain/__init__.py и tests/test_value_objects.py.
```

---

## Самопроверка

Выполните в терминале (или через `!`-команду / второй терминал):

```bash
opencode debug config | grep -A4 '"formatter"'
opencode debug config | grep domain-style
just check && just test
uv run python -c "from books_api.domain import ISBN; print(ISBN('978-3-16-148410-0'))"
opencode stats --project . --cost --models | head -20
```

Чеклист результата:

- [ ] В корне проекта лежит `opencode.jsonc` с `$schema`, `"formatter": true` и массивом `instructions`, и `opencode debug config` показывает слитый результат с этими настройками.
- [ ] В TUI при запуске с `OPENCODE_CLI_CONFIG_CONTENT='{"debug":{"turn_tokens":true}}'` виден per-turn расход токенов, и вы понимаете, почему эта настройка — в `cli.json`, а не в `opencode.jsonc`.
- [ ] В `src/books_api/domain/value_objects.py` реализованы `BookFormat`, `LanguageCode`, `ISBN`, `LicenseType`; все VO — `@dataclass(frozen=True, slots=True)` с валидацией в `__post_init__` и доменными ошибками (`ValidationError`, `LicenseViolationError`); все экспортированы через `__all__`.
- [ ] `tests/test_value_objects.py` проверяет нормализацию, контрольную цифру ISBN, свойства лицензий и `from_string`; `just check` и `just test` завершаются с кодом `0`.
- [ ] В транскрипте сессии вы видели, что OpenCode сам отформатировал файлы после `write`/`edit` (заметки форматтера у тулов), — и файлы в репозитории соответствуют `ruff format`.

---

## Шпаргалка урока

| Файл / Команда / Клавиша | Назначение |
|---|---|
| `./opencode.jsonc` (`"$schema": "https://opencode.ai/config.json"`) | Серверно-проектный конфиг: `model`, `formatter`, `instructions`, `permissions`, `mcp`, `warming` и др. |
| `~/.config/opencode/cli.json` (`"$schema": "https://opencode.ai/v2/cli.json"`) | Настройки только терминального клиента: тема, keybinds, вкладки, `diffs`, `debug.turn_tokens` |
| `OPENCODE_CLI_CONFIG_CONTENT='{"...":...}' opencode` | Inline-настройки CLI поверх `cli.json` без правки файла |
| Иерархия слияния | глобальный → корневые `opencode.jsonc` (от дальних к ближним) → `.opencode/opencode.jsonc` (перекрывает корневые) |
| `{env:VAR}` / `{file:path}` | Подстановки переменной окружения / содержимого файла в строковых значениях конфига |
| `opencode reload` | Перегрузка конфигурации без рестарта сервера (в TUI — `location.reload` через палитру `Ctrl+P`) |
| `Ctrl+X` + `M` (`/models`) | Каталог моделей; выбор — только для текущей сессии, конфиг не переписывается |
| `Ctrl+T` (`variant.cycle`) / `F2` | Цикл по вариантам модели (`provider/model#variant`) / по недавним моделям (`Shift+F2` — назад) |
| `"formatter": true` | Автоформатирование файлов после `write`/`edit`/`patch` встроенными форматтерами (`.py` → `ruff`) |
| `"instructions": [...]` | Дополнительные файлы инструкций, загружаемые наряду с `AGENTS.md` |
| `"warming": true` | Удержание prompt-кэша провайдера периодическими transient-запросами (платные; по умолчанию выключено) |
| `opencode stats --project . --cost --models` | Затраты и токены по проекту с разбивкой по моделям |
| `"debug": {"turn_tokens": true}` в `cli.json` | Per-turn расход токенов в футере TUI (`"verbose"` — ещё и входы тулов) |

Следующий шаг: **[Урок 03. Plan-режим, steering на ходу, `/btw`, снапшоты `/undo` и ревью в `/diff` →](03-plan-mode-steering-snapshots-and-diff.md)**
