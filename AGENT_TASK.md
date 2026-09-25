# Задача: реализовать MCP-сервер «Бажовский справочник»

## Контекст
Учебное ДЗ (task.md): MCP-сервер с 2–4 инструментами, каждый со схемой
входа и структурированным JSON-результатом. Домен: сказ Бажова — герои,
места действия, годы/сборники. Цель сервера: помогать LLM генерировать
новые сказки, подставляя канонных героев, места и мотивы (подход Context7:
resolve → fetch docs).

## Стек и ограничения
- Python 3.10+, официальный SDK `mcp[cli]` (FastMCP), транспорт **stdio**.
- Никаких внешних API/эмбеддингов/тяжёлых зависимостей (без pymorphy2, без сети).
- Данные — только локальные JSON в `data/`, никаких скрейпингов.

## Структура
```
server.py            # FastMCP, регистрация 4 инструментов
store.py             # загрузка JSON, validation, поиск
data/stories.json    # ~15 сказов: title, year, collection, motifs, links[]
data/characters.json # ~20 героев: name, aliases[], description, links[]
data/places.json     # ~10 мест: name, prototype, links[]
tests/               # pytest
README.md            # подключение к IDE + демо-промпты
pyproject.toml       # deps: mcp[cli], pytest
```

## Модель данных
- id — слаги с типом: `story:malakhitovaya-shkatulka`, `char:khozyayka-mednoy-gory`,
  `place:mednaya-gora`.
- Двусторонние связи: сказ↔герои↔места↔сборник/год во всех карточках (`links[]`).
- При старте сервер обязан валидировать JSON и что каждый id из `links[]` существует;
  при битой ссылке — понятная ошибка запуска.

## Инструменты (ровно 4)
1. `bazhov_resolve(query: str, type?: "story"|"character"|"place")`
   → список `{id, title, type, summary}` — этап resolve.
2. `bazhov_get(id: str)` → полная карточка со всеми полями и resolved-связями
   (по id из links[] подтягиваются title).
3. `bazhov_search(keywords: str, type?: ..., year_from?: int, year_to?: int)`
   → матчинг токенов по name+aliases+motifs (нормализация регистра/ё→е);
   при 0 совпадений — `{results: [], candidates: топ-5 по difflib}`, не ошибка.
4. `bazhov_context(theme: str)` → генерационный пакет: `{characters[], places[],
   stories[], years[], motifs[]}` — сущности, релевантные теме, со ссылками друг на друга.

Все инструменты: понятное описание + входная схема; результат — MCP
`structuredContent` (JSON-объект) плюс краткий текстовый блок.

## Поиск (без морфологии — осознанно)
- Нижний регистр, ё→е, разбиение на токены, вхождение токенов запроса в name/aliases/motifs.
- Падежи не стеммятся: спасают `aliases[]` у каждой сущности + кандидаты difflib при промахе.

## Тесты (pytest)
- загрузка и validation данных; падение на битой ссылке;
- resolve/get/search/context на реальных данных, включая: запрос в другом падеже →
  candidates; фильтрация по годам; `bazhov_context("самоцветы")` возвращает связанных героя и место.

## README
- установка (uv/pip), запуск `python server.py`;
- готовый сниппет конфига подключения для Claude Desktop/opencode/Cursor (stdio);
- 3 демо-промпта, один из них: «сгенерируй новый сказ про ...», демонстрирующий
  вызовы инструментов модели.

## Критерии приёмки
1. `python server.py` стартует без ошибок и валидирует данные.
2. Клиент (любой MCP-клиент, напр. `npx @modelcontextprotocol/inspector python server.py`)
   видит 4 инструмента со схемами.
3. Каждый инструмент возвращает структурированный JSON, а не голый текст.
4. pytest зелёный.
5. README позволяет воспроизвести демо без чтения кода.
