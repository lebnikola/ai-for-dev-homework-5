from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections import Counter
from typing import Any, Callable

from mcp.server.mcpserver import MCPServer

from store import BazhovStore

logger = logging.getLogger("bazhov-mcp")


def _setup_logging() -> None:
    level = os.environ.get("BAZHOV_LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [bazhov-mcp] %(message)s")
    )
    logger.setLevel(level)
    logger.propagate = False
    logger.addHandler(handler)


_setup_logging()

logger.info("loading data from data/*.json ...")
try:
    store = BazhovStore.load()
except Exception:
    logger.exception("data validation failed, server cannot start")
    raise
_counts = Counter(ent["type"] for ent in store.entities.values())
logger.info(
    "loaded %d entities (story=%d, character=%d, place=%d)",
    len(store.entities),
    _counts["story"],
    _counts["character"],
    _counts["place"],
)


def _instrument(name: str, fn: Callable[..., Any], **kwargs: Any) -> dict[str, Any]:
    started = time.perf_counter()
    logger.info("%s <- %s", name, json.dumps(kwargs, ensure_ascii=False))
    try:
        result = fn(**kwargs)
    except Exception as exc:
        logger.error("%s failed: %s", name, exc)
        raise
    elapsed_ms = (time.perf_counter() - started) * 1000
    if "results" in result:
        summary = f"{len(result['results'])} results, {len(result.get('candidates', []))} candidates"
    elif "id" in result:
        summary = f"id={result['id']}"
    else:
        summary = (
            f"{len(result['stories'])} stories, {len(result['characters'])} characters, "
            f"{len(result['places'])} places"
        )
    logger.info("%s -> %s (%.1f ms)", name, summary, elapsed_ms)
    logger.debug("%s full result: %s", name, json.dumps(result, ensure_ascii=False))
    return result

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
    return _instrument("bazhov_resolve", store.resolve, query=query, entity_type=entity_type)


@mcp.tool()
def bazhov_get(id: str) -> dict[str, Any]:  # noqa: A002
    """Вернуть полную карточку сущности по id (story:..., char:... или place:...).

    Связи characters/places/stories уже раскрыты в объекты {id, title, type, summary}.
    Для сказов содержит год публикации, сборник, краткое содержание и мотивы.
    """
    return _instrument("bazhov_get", store.get, entity_id=id)


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
    return _instrument(
        "bazhov_search",
        store.search,
        keywords=keywords,
        entity_type=entity_type,
        year_from=year_from,
        year_to=year_to,
    )


@mcp.tool()
def bazhov_context(theme: str) -> dict[str, Any]:
    """Собрать генерационный контекст по теме (например 'самоцветы' или 'хитрая мастерская').

    Возвращает characters, places, stories, years и motifs — связанные между собой факты
    для сочинения новой сказки в стиле Бажова.
    """
    return _instrument("bazhov_context", store.context, theme=theme)


if __name__ == "__main__":
    logger.info("starting MCP server 'bazhov-reference' (transport=stdio)")
    mcp.run(transport="stdio")
    logger.info("server stopped")
