# Бажовский справочник — MCP-сервер

MCP-сервер справочника по сказам П. П. Бажова: сказы, герои и места Урала.
Помогает основной LLM генерировать новые сказки в стиле Бажова, выдавая проверенные
факты вместо «галлюцинаций» (Context7-подобный поток: `resolve → get`).

## Инструменты

Краткая запись сущности — `{id, title, type, summary}`; у сказов в `summary` указан год:
«Каменный цветок (1938)». Все инструменты возвращают JSON-объект, и он же дублируется в
поле MCP-ответа `structuredContent`.

| Инструмент | Назначение | Результат |
| --- | --- | --- |
| `bazhov_resolve(query, entity_type?)` | Поиск по названию и алиасам | `{results: [краткая], candidates: []}` |
| `bazhov_search(keywords, entity_type?, year_from?, year_to?)` | Поиск по названию, алиасам, мотивам и описаниям; с годовым фильтром возвращаются только сказы | как у `bazhov_resolve` |
| `bazhov_get(id)` | Полная карточка: все поля из `data/*.json`, связи `characters`/`places`/`stories` раскрыты в краткие записи | карточка сущности |
| `bazhov_context(theme)` | Пакет фактов для нового сказа: начальные сущности из результатов поиска (при пустом `results` — из `candidates`) и их связанные персонажи, места и сказы | `{characters, places, stories, years, motifs}`, где списки — краткие записи |

`results` отсортирован по релевантности, затем по названию. `candidates` (difflib, не более
5) непустой только при пустом `results`. Допустимые `entity_type`: `story`, `character`,
`place`; id при этом — `story:...`, `char:...`, `place:...`.

Ошибки (неизвестный id, пустой запрос, неверный `entity_type`) приходят как tool-error с
текстом сообщения об ошибке.

## Данные

Локальные JSON в `data/` (без внешних API при runtime):

- `data/stories.json` — 15 сказов (год, сборник, краткое содержание, мотивы)
- `data/characters.json` — 27 героев (алиасы, описания)
- `data/places.json` — 8 мест (прототипы реальных уральских объектов)

При старте сервер валидирует схемы и все `links[]`: несуществующий id → ошибка запуска.
Поиск регистронезависимый, `ё` → `е`.

## Установка

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python "mcp[cli]>=2.2" pytest
```

## Запуск и демо-сессия

Транспорт — stdio:

```bash
.venv/bin/python server.py            # «сырой» запуск
npx @modelcontextprotocol/inspector .venv/bin/python server.py   # интерактивная проверка
```

Подключение к MCP-клиенту (Claude Desktop / opencode и т. п.):

```json
{
  "mcpServers": {
    "bazhov-reference": {
      "command": "/абсолютный/путь/homework5/.venv/bin/python",
      "args": ["/абсолютный/путь/homework5/server.py"]
    }
  }
}
```

Демонстрационные запросы (в inspector или через `scripts/smoke_client.py`):

1. `bazhov_resolve("хозяйка медной горы")` → находит и сказ, и персонажа.
2. `bazhov_get("story:kamenny-tsvetok")` → карточка 1938 г. со связями: Данила-мастер,
   Катерина, Прокопьич, Хозяйка Медной горы, Медная гора.
3. `bazhov_search("жадность", entity_type="story", year_from=1936)` → «Приказчиковы
   подошвы», «Сочневы камешки» и т. п.
4. `bazhov_context("самоцветы")` → Кокованя, Дарёнка, Хозяйка, Серебряное копытце,
   места Красногорка/Медная гора, годы 1937–1938, мотивы.
5. Опечатка: `bazhov_search("кокований")` → `results: []`, `candidates`: `char:kokovanya`,
   `char:muryonka`.

Пример промпта для основной модели после получения контекста:
«Используя bazhov_context("самоцветы"), сочини новый сказ про Дарёнку: героиня, место,
искушение богатством и мораль Бажова».

## Логи / отладка

Вся серверная отладка пишется в **stderr** (stdout занят JSON-RPC протоколом):

- старт: загрузка и валидация `data/*.json` с количеством сущностей; при ошибке валидации — traceback;
- каждый вызов инструмента: аргументы (`<-`) и итог с длительностью (`-> ... (X ms)`);
- ошибки инструментов логируются перед возвратом ошибки клиенту.

Уровень настраивается переменной `BAZHOV_LOG_LEVEL` (по умолчанию `INFO`;
`DEBUG` дополнительно пишет полный JSON каждого ответа):

```bash
BAZHOV_LOG_LEVEL=DEBUG .venv/bin/python server.py 2>server.log   # логи в файл
npx @modelcontextprotocol/inspector .venv/bin/python server.py    # stderr сервера виден во вкладке Server output
.venv/bin/python scripts/smoke_client.py                          # логи сервера проходят через его stderr
```

## Тесты

```bash
.venv/bin/python -m pytest -q              # юнит-тесты store (14 тестов)
.venv/bin/python scripts/smoke_client.py   # сквозной прогон через stdio
```

## Структура проекта

```
server.py                # MCPServer (mcp 2.x), stdio
store.py                 # загрузка data/*.json, валидация связей, поиск, context
data/                    # stories.json, characters.json, places.json
tests/test_store.py      # юнит-тесты хранилища и поиска
scripts/smoke_client.py  # сквозная проверка MCP-протокола
отчет.md                 # отчёт о выполнении ДЗ: критерии + ссылки на код
AGENT_TASK.md            # спецификация реализации
```
