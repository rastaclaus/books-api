# Урок 10. Серверные плагины, headless CLI `opencode run`, HTTP API и Web UI

[← Урок 09. Параллельные сабагенты и Git worktrees](09-parallel-subagents-and-worktrees.md) | [Карта курса](README.md)

## Цель урока

- Освоить **серверные плагины OpenCode V2**: локальные плагины в `.opencode/plugins/`, API `Plugin.define`, plugin context как клиент сервера и рантайм-хуки `ctx.tool.hook` / `ctx.permission.hook` — программируемый аналог защитных правил проекта.
- Научиться headless-автоматизации: неинтерактивный **`opencode run`** для скриптов и CI (`--model`, `--agent`, `--format json`, `--auto`, `--archived`, `--standalone`).
- Познакомиться с остальными интерфейсами того же фонового сервера: `opencode mini`, `opencode pair` и Web UI, `opencode serve`, HTTP API (`opencode api`), `opencode stats`, `opencode reload`.
- Собрать финальную документацию домена `docs/domain-architecture.md`, включить плагин-стража чистоты в контур проекта и подвести итоги всего курса.

---

## Теория-минимум: плагины как «прошивка» сервера и CLI как универсальный клиент

### Серверные плагины V2

Плагин — это модуль, который меняет поведение OpenCode и добавляет новые возможности. Серверная часть плагина выполняется **внутри фонового сервера** и может добавлять тулы, хуки, интеграции, команды и агентов. Пакет плагина может включать серверную часть, TUI-часть, GUI-часть (или любую комбинацию), но в этом курсе мы используем только серверную часть.

Плагины, лежащие в **`.opencode/plugins/`, подхватываются автоматически**. Формы:

- каталог `.opencode/plugins/<имя>/index.ts` (или `index.js`);
- одиночные `.ts`/`.js`-файлы прямо в `.opencode/plugins/`.

Опубликованные пакеты и плагины из других мест подключаются массивом `plugins` в `opencode.jsonc`. При объектной форме элемента `{ package, options }` плагин получает свои настройки через `ctx.options`.

Минимальный скелет серверного плагина:

```ts
import { Plugin } from "@opencode/plugin"

export default Plugin.define({
  id: "example",
  setup(ctx) {
    console.log(`loaded in OpenCode ${ctx.app.version}`)
    return () => console.log("unloaded") // cleanup при выгрузке плагина
  },
})
```

Ключевые факты об API:

- **`Plugin.define({ id, setup(ctx) })`** — единственная точка входа серверной части. `setup` выполняется при загрузке плагина и **может вернуть cleanup-функцию**, которая вызовется при выгрузке (выгрузка происходит при dispose-регистраций, правках конфига и т. п.).
- **Plugin context — это клиент сервера OpenCode.** Методы чтения и действий принимают те же входы и возвращают те же ответы, что и клиент. Дополнительно доступны plugin-only методы: трансформы, рантайм-хуки, reload-ы, регистрация и опции плагина. Из `ctx` доступны, например, `ctx.app.version`, `ctx.location` (директория и метаданные проекта, где загружен экземпляр плагина), `ctx.options` (при объектной форме подключения), `ctx.storage` (долговременные JSON-значения), `ctx.session.*`, `ctx.event.subscribe`.
- **Трансформы** — синхронные правки доменного состояния сервера: `ctx.tool.transform` (регистрация/правка тулов), `ctx.agent.transform` (агенты и дефолтный агент), `ctx.mcp.transform` (MCP-серверы), плюс провайдеры, модели, команды, скиллы, worktree-стратегии и др. Каждый трансформ достраивается на предыдущих; при изменении captured-входов вызывают `reload()` соответствующего домена. В этом уроке мы упоминаем их кратко — наша цель рантайм-хуки.

### Рантайм-хуки: `ctx.tool.hook` и `ctx.permission.hook`

Хуки перехватывают живые операции. Регистрация хука возвращает registration, которую можно dispose-ить; несколько плагинов могут регистрировать один хук — они выполняются в порядке плагинов, и поздние видят изменения ранних.

**Tool-хуки** — осмотр и замена входа тулов до выполнения и результата после:

- `ctx.tool.hook("execute.before", (event) => ...)` — `event.tool` (имя тула) и `event.input` (вход тула). Если callback бросит исключение, выполнение тула прервётся — это и есть механизм жёстких запретов.
- `ctx.tool.hook("execute.after", (event) => ...)` — `event.status` равен `"completed"` (можно доработать `event.result`) или `"error"` (есть `event.error`).

**Permission-хук** `ctx.permission.hook("evaluate", ...)` — ревизия решений о разрешениях *после* оценки настроенных правил и *до* выполнения действия или публикации запроса на разрешение:

- событие несёт `event.action` (действие, например `"edit"`, `"shell"`), `event.resources` (список затрагиваемых значений — путей, команд и т. п.) и текущий `event.effect`;
- хук вызывается для решений `allow` и `ask`; **явный `deny` из правил финален и хук не вызывает**;
- хук **может менять `effect`** на `allow`, `ask` или `deny`; `event.message` появляется в эскалированном запросе на разрешение или становится причиной отказа.

В этом сила V2 по сравнению с внешними shell-скриптами (как `JCODE_HOOK_*` в курсе jcode): хук работает **внутри сервера**, получает типизированные события и может не просто логировать, а прямо изменять решение о разрешении.

Кратко о трансформах: `ctx.tool.transform` регистрирует собственные тулы, `ctx.agent.transform` правит агентов и дефолтного агента, `ctx.mcp.transform` — MCP-серверы (`editor.set/update/remove`). Полезно знать, что такие точки расширения существуют, — они пригодятся вам уже за пределами курса.

### Headless-автоматизация: `opencode run`

`opencode run "промпт"` отправляет сообщение и печатает ответ **без интерактивного интерфейса**. Он спроектирован для скриптов, CI-джобов и любых workflow, которым нужен ответ модели прямо в терминале:

```bash
opencode run "Explain this repository"
```

Основные флаги:

| Флаг | Назначение |
|---|---|
| `--model provider/model` (и `#variant`) | Выбрать модель для этого запуска |
| `--agent <id>` | Запустить с конкретным агентом (например, read-only `explore`) |
| `--format json` | Печатать **NDJSON** — построчный поток JSON-событий для скриптов |
| `--file <путь>` | Прикрепить файл к сообщению (можно несколько раз) |
| `--continue` | Продолжить последнюю сессию |
| `--session ses_...` | Продолжить конкретную сессию |
| `--auto` | Автоподтверждать разрешения, которые явно не запрещены правилами |
| `--archived` | Создать сессию **архивной**: она не засоряет список сессий и inbox в TUI, но существует и доступна по ID (`opencode session list` её показывает) |
| `--standalone` | Запуск с **приватным сервером** вместо общего фонового: для CI, чтобы секреты (ключ провайдера через env) получал именно этот приватный сервер |

Канонический CI-пример из документации — GitHub Actions ревьюит checked-out репозиторий:

```yaml
name: OpenCode review
on: [pull_request]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm install --global @opencode/cli
      - run: opencode run --standalone --model anthropic/ "Review this repository for correctness and summarize any issues."
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

### Прочие интерфейсы сервера

Клиент-серверная архитектура, которую мы наблюдали с первого урока, означает: TUI — лишь один из клиентов. Тот же сервер обслуживает:

- **`opencode mini`** — минимальный интерактивный режим вместо полноэкранного TUI (есть свои `--model`, `--prompt`, `--session`, `--continue`; полный список — `opencode mini --help`).
- **`opencode pair`** — одноразовая ссылка (+QR-код) для подключения браузера или приложения OpenCode: ссылки работают один раз и истекают через 5 минут. Web UI отдаётся тем же сервером, что и TUI, и защищён паролем. По умолчанию сервер слушает `localhost:49374` (macOS/Linux/WSL; адрес печатает `opencode service status`). Пароль сервера задаётся через `opencode service set password "..."`; `opencode pair --remote` публикует сервер через туннель с шифрованием.
- **`opencode serve`** — тот же сервер в foreground (для явного управления): `opencode serve --hostname 0.0.0.0 --port 4096`.
- **HTTP API** — все клиенты ходят в сервер по HTTP; справочник — OpenAPI 3.1.0 на `/openapi.json`. CLI-команда `opencode api` делает запросы к работающему серверу: `opencode api GET /api/session`, вызов по operationID (`opencode api session.list --param limit=10`), с JSON-телом (`--data`) и заголовками (`-H`).
- **`opencode stats`** — отчёт об использовании: `--models` (модели), `--cost` (стоимость и токены), `--json` (JSON вместо отчёта), `--days N`, `--project .`.
- **`opencode reload`** — перезагрузка конфигурации без рестарта сервера; идущие сессии продолжают работу с свежими сервисами на ближайшей границе шага.

### Где смотреть, когда что-то не так

- Логи установленной сборки пишутся в `~/.local/share/opencode/log/opencode.log`; каждая строка несёт process-`run` ID и поле `role` (для сессий, провайдеров, плагинов, разрешений и тулов фильтруйте `role=server`). Уровень логирования поднимается, например, `opencode service set env OPENCODE_LOG_LEVEL DEBUG` (затем `opencode service start`).
- Состояние фонового сервера: `opencode service status`; рестарт: `opencode service restart`.

---

## Практика шаг за шагом

### Шаг 1. Создайте плагин-стража чистоты домена

Мы уже защищали домен декларативно — `permissions` в `opencode.jsonc` (Урок 08) и AST-скриптом `check_purity.py` из Урока 06. Теперь добавим **программный** слой: плагин, который внутри сервера отклоняет правки, содержащие запрещённые импорты, и логирует все вызовы пишущих тулов.

Попросите агента в TUI (или создайте файл сами) положить плагин по пути `.opencode/plugins/domain-guard/index.ts`:

```text
Создай серверный плагин OpenCode V2 в файле .opencode/plugins/domain-guard/index.ts.

Требования к коду:
1. Точка входа: import { Plugin } from "@opencode/plugin" и export default Plugin.define({ id: "domain-guard", setup(ctx) { ... } }).
2. В setup зарегистрируй ctx.permission.hook("evaluate", ...) — асинхронный колбэк с event:
   - если event.action === "edit" и какой-либо ресурс из event.resources содержит "src/books_api/domain/":
   - просканируй путь на запрещённые пакеты: fastapi, flask, django, sqlalchemy, sqlite3, httpx, requests;
   - при обнаружении выставь event.effect = "deny" и event.message = `domain-guard: '<пакет>' запрещён в чистом домене — только стандартная библиотека Python`.
3. Также зарегистрируй ctx.tool.hook("execute.before", ...) — если event.tool === "write" или event.tool === "edit", логируй в console.log строку с именем тула и входом (JSON.stringify(event.input)).
4. Плагин должен использовать только API V2: Plugin.define, setup(ctx), ctx.permission.hook и ctx.tool.hook. Никаких legacy-хуков V1 ("tool.execute.before" и т. п.).
```

Эталонный листинг плагина (сверьтесь):

```ts
// .opencode/plugins/domain-guard/index.ts
import { Plugin } from "@opencode/plugin"

const DOMAIN_ROOT = "src/books_api/domain/"
const FORBIDDEN = ["fastapi", "flask", "django", "sqlalchemy", "sqlite3", "httpx", "requests"] as const

export default Plugin.define({
  id: "domain-guard",
  setup(ctx) {
    // 1. Ревизия решений о разрешениях: отклоняем правки домена с чужими импортами.
    ctx.permission.hook("evaluate", (event) => {
      if (event.action !== "edit") return

      const inDomain = event.resources.some((resource) => resource.includes(DOMAIN_ROOT))
      if (!inDomain) return

      for (const pkg of FORBIDDEN) {
        if (event.resources.some((resource) => resource.toLowerCase().includes(pkg))) {
          event.effect = "deny"
          event.message = `domain-guard: '${pkg}' запрещён в чистом домене — только стандартная библиотека Python`
          return
        }
      }
    })

    // 2. Журнал вызовов пишущих тулов (хук срабатывает на входе тула).
    ctx.tool.hook("execute.before", (event) => {
      if (event.tool === "write" || event.tool === "edit") {
        console.log(`[domain-guard] ${event.tool}: ${JSON.stringify(event.input)}`)
      }
    })
  },
})
```

Обратите внимание на два уровня защиты:

- **`execute.before` — это наблюдение, а не гарантия.** Хук срабатывает на *входе* тула (аргументы), и модель может обойти наивный строковый поиск, например, собрав импорт динамически. Поэтому он надёжнее комбинируется с AST-скриптом `check_purity.py` из Урока 06 и ruff-правилами в `just check` — программный слой плагина дополняет детерминированные проверки, а не заменяет их.
- **`permission.hook("evaluate")` — это решение.** Оно выполняется после правил `permissions` из конфига и может отклонить действие с понятной модели причиной (`event.message` попадает в отказ).

Проверьте, что плагин загрузился: в новой сессии TUI плагин подхватится автоматически; убедиться в его активности можно по логам сервера:

```bash
tail -f ~/.local/share/opencode/log/opencode.log | grep 'role=server'
```

### Шаг 2. Провокационный тест плагина

Проверим стража в бою. В интерактивной сессии отправьте провокационный промпт:

```text
Для эксперимента добавь `import sqlite3` в начало src/books_api/domain/catalog.py; если сработает защита проекта, ничего не ломай и объясни причину отказа.
```

Ожидаемое поведение: агент попытается править файл в `src/books_api/domain/`, permission-хук обнаружит `sqlite3` в ресурсах и выставит `effect = "deny"`; агент получит отказ с вашим сообщением (`domain-guard: 'sqlite3' запрещён в чистом домене — только стандартная библиотека Python`) и объяснит вам причину отказа, не внёс изменения. В логе сервера при этом появится строка `[domain-guard] edit: ...` от tool-хука.

Если защита не сработала — проверьте: (1) файл лежит в `.opencode/plugins/domain-guard/index.ts`; (2) сессия перезапущена после создания плагина (`opencode reload` или новая сессия); (3) `event.action` действительно `"edit"` — посмотрите фактические события в логе.

### Шаг 3. Сгенерируйте финальную документацию домена

Домен books-api собран за девять уроков. Зафиксируем его карту для будущих разработчиков:

```text
Изучи все модули src/books_api/domain/ и создай docs/domain-architecture.md:
1. Mermaid-диаграмма классов и взаимодействий: Book, Author, BookAsset, Reader, LicenseType, ISBN, BookFormat, DownloadService, CatalogQuery, BookRepository, InMemoryBookRepository, Anthology, LicensePolicy.
2. Таблица всех бизнес-инвариантов (с указанием модуля и метода, который их защищает) и подклассов DomainError с их назначением.
3. Пример использования публичного API домена в 15-20 строках Python (создание книги с автором и ассетами, запрос на скачивание через DownloadService, сборная антология через LicensePolicy).
Перед завершением прогони just check и just test.
```

Откройте `docs/domain-architecture.md`, оцените полноту диаграммы и таблицы инвариантов — это итоговая самодокументация вашего домена, сгенерированная агентом из кода.

### Шаг 4. CI-аудит домена через `opencode run`

Соберём всё в headless-скрипт: детерминированные проверки (`just check`, `just test`) плюс LLM-аудит архитектуры через read-only агента `explore` из Урока 08. Создайте `scripts/ci_domain_audit.sh`:

```text
Создай исполняемый скрипт scripts/ci_domain_audit.sh со следующим содержимым:

#!/usr/bin/env bash
set -euo pipefail

echo "1/3 Running linters and strict type check (just check)..."
just check

echo "2/3 Running unit tests (just test)..."
just test

echo "3/3 Running read-only OpenCode architectural audit (headless)..."
# --archived: сессия аудита не попадёт в список сессий TUI.
# --agent explore: read-only сабагент, правки невозможны.
# --format json: NDJSON-поток событий; формат событий может отличаться
#   между версиями — при отладке посмотрите сырой вывод командой без пайпа.
# В CI добавьте --standalone и передавайте ключ провайдера через env
# (см. пример GitHub Actions в теории урока).
opencode run --archived --agent explore --format json \
  "Verify that src/books_api/domain/ contains only pure Python domain code with zero web/DB imports and consistent DomainError subclasses. End your reply with exact line STATUS: PASS or STATUS: FAIL." \
  | python3 -c 'import json,sys; [print(json.loads(l).get("text","") or json.loads(l).get("part",{}).get("text","")) for l in sys.stdin if l.strip()]' \
  | grep -q "STATUS: PASS"
```

⚠️ Комментарий по надёжности: формат NDJSON-событий (`--format json`) может отличаться между версиями OpenCode — extractor на Python выше написан с запасом (`text` или вложенный `part.text`), но перед использованием в реальном CI посмотрите сырой вывод команды без пайпа и при необходимости поправьте extractor. В CI-окружении запускайте с `--standalone` (приватный сервер), передавая ключ провайдера через переменную окружения, как в примере GitHub Actions выше.

Сделайте скрипт исполняемым и запустите:

```bash
chmod +x scripts/ci_domain_audit.sh
./scripts/ci_domain_audit.sh
```

Все три ступени должны быть зелёными: линтеры, тесты и LLM-аудит, завершившийся строкой `STATUS: PASS`.

### Шаг 5. Осмотритесь в остальных интерфейсах сервера

Во втором терминале (или через shell-режим `!` в TUI) попробуйте:

```bash
opencode api GET /api/session       # список сессий через HTTP API
opencode stats --cost --models      # стоимость и модели за последние дни
```

Для `opencode api` альтернативой пути служит operationID из OpenAPI-справочника:

```bash
opencode api session.list --param limit=10
```

Полный справочник эндпоинтов и схем — OpenAPI-документ на `/openapi.json` вашего сервера (адрес печатает `opencode service status`).

Затем попробуйте минимальный интерактивный режим:

```bash
opencode mini
```

Это та же сессия и те же агенты, но без полноэкранного TUI — удобно в панелях терминала и по SSH.

Наконец, подключите Web UI:

```bash
opencode pair
```

Команда напечатает одноразовую ссылку вида `http://127.0.0.1:49374/auth/connect/...` и QR-код. Откройте ссылку в браузере: вы войдёте в **Web UI** того же фонового сервера — те же сессии, агенты и настройки, что и в TUI, но в браузере. Ссылка работает один раз и истекает через 5 минут; пароль сервера (если хотите заменить сгенерированный) задаётся `opencode service set password "ваш-секрет"`, после смены пароля все web-сессии выйдут.

### Шаг 6. Финальный коммит

Зафиксируйте финальные артефакты курса:

```text
/commit
```

Или, если вы пропустили Урок 05, попросите агента явно:

```text
Проанализируй git status и git diff, создай финальный коммит в стиле Conventional Commits: плагин .opencode/plugins/domain-guard/, docs/domain-architecture.md и scripts/ci_domain_audit.sh.
```

---

## Самопроверка

Выполните в терминале:

```bash
just check
just test
./scripts/ci_domain_audit.sh
opencode stats --cost --models
opencode api GET /api/session | head -5
```

Чеклист результата:

- [ ] `.opencode/plugins/domain-guard/index.ts` создан по форме `Plugin.define({ id, setup(ctx) })`, подхватывается автоматически, и его permission-хук отклоняет провокацию `import sqlite3` в `src/books_api/domain/` с вашим сообщением об отказе.
- [ ] В логе `~/.local/share/opencode/log/opencode.log` видны записи `[domain-guard]` от tool-хука при вызовах `write`/`edit`.
- [ ] `docs/domain-architecture.md` содержит mermaid-диаграмму домена, таблицу инвариантов и ошибок `DomainError` и пример использования API.
- [ ] `scripts/ci_domain_audit.sh` исполняемый, проходит три ступени и завершается `STATUS: PASS`; сессия аудита не появилась в списке сессий TUI (`--archived`).
- [ ] Вы поработали с `opencode api` (запрос к `/api/session` или по operationID), `opencode stats`, `opencode mini` и `opencode pair` (Web UI открылся в браузере).

---

## Финальный чеклист: чему вы научились за 10 уроков

Поздравляем! Вы с нуля построили чистую, строго типизированную и протестированную доменную модель `books-api` и на практике освоили полный арсенал настроек и фич OpenCode V2.

### Настройки уровня проекта в репозитории

- [x] **`./AGENTS.md`** и живое обновление инструкций без перезапуска сессии (Урок 01).
- [x] **`./opencode.jsonc` vs `~/.config/opencode/cli.json`**: серверно-проектный конфиг против терминальных настроек TUI, `formatter`, `instructions`, `warming` (Урок 02).
- [x] **`experimental.todo`, агенты Plan/Build** и переключение режимов планирования и сборки (Урок 03).
- [x] **`compaction`** для долгих сессий, вложенные `AGENTS.md` и внешние `references` (Урок 04).
- [x] **`.opencode/commands/*.md`** и shell-инъекции `` !`команда` `` в шаблонах кастомных slash-команд (Урок 05).
- [x] **`.opencode/skills/<id>/SKILL.md`** с приватными `references/` и `scripts/` (Урок 06).
- [x] **`mcp.servers`** и Code Mode: композиция тулов и MCP-вызовов внутри `execute` (Урок 07).
- [x] **`.opencode/agents/*.md`** и декларативные `permissions`/`policies` для безопасного агента (Урок 08).
- [x] **Git worktrees** для изолированных экспериментов и параллельных сессий (Урок 09).
- [x] **`.opencode/plugins/`** (`Plugin.define`, рантайм-хуки) и headless-интерфейсы `opencode run` / `opencode api` / `opencode pair` (Урок 10).

### Продвинутые режимы управления

- [x] Steering и queue для сообщений на лету, боковые вопросы `/btw`, snapshots с `/undo` / `/redo` и ревью изменений `/diff` со scope `turn` / `working` / `branch` (Урок 03).
- [x] Фоновые сабагенты с отслеживанием по `sessionID` и уведомлениями `<subagent>` (Урок 09).
- [x] Независимое read-only ревью кастомным агентом-ревьюером (Урок 08).
- [x] Headless-автоматизация: `opencode run --format json --archived` для скриптов и CI, с `--standalone` для приватных серверов с секретами (Урок 10).

Теперь вы можете переносить этот же набор практик — живой `AGENTS.md`, декларативный `opencode.jsonc`, кастомные команды и скиллы, read-only ревьюеров, permission-правила и плагины-стража, headless-аудиты в CI — в свои реальные рабочие репозитории. Удачных проектов с OpenCode V2!

---

## Шпаргалка урока

| Команда / Файл | Назначение |
|---|---|
| `.opencode/plugins/<имя>/index.ts` | Локальный серверный плагин, подхватывается автоматически (возможны и одиночные `.ts`/`.js` в `.opencode/plugins/`) |
| `Plugin.define({ id, setup(ctx) })` | Точка входа плагина V2; `setup` может вернуть cleanup-функцию |
| `ctx` (plugin context) | Клиент сервера: `ctx.app.version`, `ctx.location`, `ctx.options`, `ctx.session.*`, `ctx.storage`, плюс plugin-only трансформы и хуки |
| `ctx.tool.hook("execute.before"/"execute.after")` | Перехват вызовов тулов: вход (`event.tool`, `event.input`) и результат (`event.status` completed/error) |
| `ctx.permission.hook("evaluate")` | Ревизия решений о разрешениях: чтение `event.action`/`event.resources`, изменение `event.effect` (allow/ask/deny) и `event.message`; явный deny из правил не вызывает хук |
| `ctx.tool.transform` / `ctx.agent.transform` / `ctx.mcp.transform` | Реестровые трансформы: регистрация тулов, правка агентов и MCP-серверов |
| `opencode run "промпт"` | Headless-запуск для скриптов и CI (`--model`, `--agent`, `--format json`, `--file`, `--continue`/`--session`, `--auto`, `--archived`, `--standalone`) |
| `opencode mini` | Минимальный интерактивный режим вместо полноэкранного TUI |
| `opencode pair` | Одноразовая ссылка (+QR) в Web UI; сервер по умолчанию на `localhost:49374`, пароль — `opencode service set password` |
| `opencode serve --hostname 0.0.0.0 --port N` | Тот же сервер в foreground |
| `opencode api GET /api/session` / `opencode api <operationID> --param ...` | HTTP API работающего сервера; справочник — `/openapi.json` |
| `opencode stats --cost --models --json` | Отчёт об использовании моделей и стоимости |
| `opencode reload` | Перезагрузка конфигурации без рестарта сервера |
| `~/.local/share/opencode/log/opencode.log`, `OPENCODE_LOG_LEVEL=DEBUG`, `opencode service status` / `restart` | Диагностика: логи сервера (фильтр `role=server`), уровень логирования, состояние и рестарт фонового сервиса |
