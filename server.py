from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from store import BazhovStore

store = BazhovStore.load()

mcp = MCPServer(
    "bazhov-reference",
    instructions=(
        "Справочник по сказам П. П. Бажова: сказы, герои и места Урала. "
        "Рабочий поток: bazhov_resolve (или bazhov_search) -> bazhov_get для полной карточки; "
        "bazhov_context — готовый пакет фактов для генерации новой сказки. "
        "id имеют вид story:..., char:..., place:...."
    ),
)


@mcp.tool()
def bazhov_resolve(query: str, entity_type: str | None = None) -> dict[str, Any]:
    """Найти сущность Бажова по названию или алиасу.

    query: название или алиас, например 'хозяйка медной горы' или 'Данила'.
    entity_type: необязательный фильтр 'story', 'character' или 'place'.
    Возвращает results (id, title, type, summary) и candidates при пустом результате.
    """
    return store.resolve(query, entity_type)


@mcp.tool()
def bazhov_get(id: str) -> dict[str, Any]:  # noqa: A002
    """Вернуть полную карточку сущности по id (story:..., char:... или place:...).

    Связи characters/places/stories уже раскрыты в объекты {id, title, type, summary}.
    Для сказов содержит год публикации, сборник, краткое содержание и мотивы.
    """
    return store.get(id)


@mcp.tool()
def bazhov_search(
    keywords: str,
    entity_type: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> dict[str, Any]:
    """Fuzzy-поиск по названию, алиасам, мотивам и описаниям.

    keywords: любые ключевые слова ('жадность самоцветов').
    entity_type: фильтр 'story', 'character' или 'place'.
    year_from/year_to: диапазон годов публикации (применяется только к сказам).
    При отсутствии совпадений возвращает candidates со схожими названиями.
    """
    return store.search(keywords, entity_type, year_from, year_to)


@mcp.tool()
def bazhov_context(theme: str) -> dict[str, Any]:
    """Собрать генерационный контекст по теме (например 'самоцветы' или 'хитрая мастерская').

    Возвращает characters, places, stories, years и motifs — связанные между собой факты
    для сочинения новой сказки в стиле Бажова.
    """
    return store.context(theme)


if __name__ == "__main__":
    mcp.run(transport="stdio")
