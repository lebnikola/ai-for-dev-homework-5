# Бажовский справочник — MCP-сервер

MCP-сервер справочника по сказам П. П. Бажова: сказы, герои и места Урала.
Помогает основной LLM генерировать новые сказки в стиле Бажова, выдавая проверенные
факты вместо «галлюцинаций» (Context7-подобный поток: `resolve → get`).

## Инструменты

| Инструмент | Назначение |
| --- | --- |
| `bazhov_resolve(query, entity_type?)` | Поиск по названию/алиасу → `{results[], candidates[]}` |
| `bazhov_get(id)` | Полная карточка с раскрытыми связями (characters/places/stories) |
| `bazhov_search(keywords, entity_type?, year_from?, year_to?)` | Fuzzy-поиск по мотивам/описаниям; при промахе — `candidates` |
| `bazhov_context(theme)` | Готовый пакет `{characters, places, stories, years, motifs}` для генерации |

Типы сущностей и id: `story:...`, `char:...`, `place:...`.

## Данные

Локальные JSON в `data/` (без внешних API при runtime):

- `data/stories.json` — 15 сказов (год, сборник, краткое содержание, мотивы)
- `data/characters.json` — 27 героев (алиасы, описания, прототипы)
- `data/places.json` — 8 мест (прототипы реальных уральских объектов)

При старте сервер валидирует схемы и все `links[]`: несуществующий id → ошибка запуска.
Поиск регистронезависимый, `ё` → `е`; опечатки лечатся списком `candidates` (difflib).

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
5. Опечатка: `bazhov_search("кокований")` → пустые `results` и `candidates`
   (`char:kokovanya`, `char:muryonka`).

Пример промпта для основной модели после получения контекста:
«Используя bazhov_context("самоцветы"), сочини новый сказ про Дарёнку: героиня, место,
искушение богатством и мораль Бажова».

## Тесты

```bash
.venv/bin/python -m pytest -q              # юнит-тесты store (14 тестов)
.venv/bin/python scripts/smoke_client.py   # stdio-клиент: 4 инструмента + structuredContent
```

## Структура проекта

```
server.py            # MCPServer (mcp 2.x), 4 инструмента, stdio
store.py             # загрузка data/*.json, валидация связей, fuzzy-поиск, context
data/                # stories.json, characters.json, places.json
tests/test_store.py  # юнит-тесты хранилища и поиска
scripts/smoke_client.py  # сквозная проверка MCP-протокола
AGENT_TASK.md        # спецификация реализации
```
