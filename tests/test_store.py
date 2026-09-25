import json
from pathlib import Path

import pytest

from store import DATA_DIR, BazhovStore, normalize


@pytest.fixture(scope="module")
def store() -> BazhovStore:
    return BazhovStore.load()


def test_load_counts(store: BazhovStore) -> None:
    stories = [e for e in store.entities.values() if e["type"] == "story"]
    characters = [e for e in store.entities.values() if e["type"] == "character"]
    places = [e for e in store.entities.values() if e["type"] == "place"]
    assert len(stories) >= 15
    assert len(characters) >= 20
    assert len(places) >= 8


def test_all_links_exist(store: BazhovStore) -> None:
    for ent in store.entities.values():
        fields = {
            "story": ("characters", "places"),
            "character": ("stories",),
            "place": ("stories",),
        }[ent["type"]]
        for field in fields:
            for link_id in ent[field]:
                assert link_id in store.entities


def test_get_resolves_links(store: BazhovStore) -> None:
    card = store.get("story:kamenny-tsvetok")
    assert card["year"] == 1938
    titles = {c["title"] for c in card["characters"]}
    assert "Данила-мастер" in titles
    assert all(isinstance(c, dict) and "id" in c for c in card["characters"])
    place_ids = {p["id"] for p in card["places"]}
    assert "place:mednaya-gora" in place_ids


def test_get_unknown_id_raises(store: BazhovStore) -> None:
    with pytest.raises(ValueError, match="unknown id"):
        store.get("story:no-such-tale")


def test_resolve_alias_case_insensitive(store: BazhovStore) -> None:
    found = store.resolve("ХОЗЯЙКА медной горы", entity_type="character")
    ids = {item["id"] for item in found["results"]}
    assert "char:khozyayka-mednoy-gory" in ids


def test_resolve_typo_returns_candidates(store: BazhovStore) -> None:
    found = store.resolve("кокований", entity_type="character")
    assert found["results"] == []
    ids = {item["id"] for item in found["candidates"]}
    assert "char:kokovanya" in ids


def test_resolve_invalid_type_raises(store: BazhovStore) -> None:
    with pytest.raises(ValueError, match="entity_type"):
        store.resolve("малахит", entity_type="wizard")


def test_search_matches_motifs_and_filters_years(store: BazhovStore) -> None:
    found = store.search("самоцветы", year_from=1937, year_to=1940)
    ids = {item["id"] for item in found["results"]}
    assert "story:sochnevy-kameshki" in ids
    assert "story:serebryanoe-kopyttse" in ids
    for item in found["results"]:
        assert item["type"] == "story"
    years = [store.entities[i]["year"] for i in ids]
    assert all(1937 <= year <= 1940 for year in years)


def test_search_typo_returns_candidates(store: BazhovStore) -> None:
    found = store.search("огневущка")
    ids = {item["id"] for item in found["candidates"]}
    assert "char:ognevushka-poskakushka" in ids or any(
        "story:ognevushka" in i for i in ids
    )


def test_search_year_filter_excludes_non_stories(store: BazhovStore) -> None:
    found = store.search("хозяйка", year_from=1936, year_to=1939)
    assert all(item["type"] == "story" for item in found["results"])


def test_context_samoцветы(store: BazhovStore) -> None:
    ctx = store.context("самоцветы")
    story_ids = {s["id"] for s in ctx["stories"]}
    char_ids = {c["id"] for c in ctx["characters"]}
    place_ids = {p["id"] for p in ctx["places"]}
    assert "story:serebryanoe-kopyttse" in story_ids
    assert "char:khozyayka-mednoy-gory" in char_ids
    assert "place:mednaya-gora" in place_ids
    assert 1938 in ctx["years"]
    assert "самоцветы" in ctx["motifs"]


def test_normalize_yo(store: BazhovStore) -> None:
    found = store.resolve("огневушка")
    ids = {item["id"] for item in found["results"]}
    assert "story:ognevushka-poskakushka" in ids
    assert normalize("Малахит") == "малахит"


def test_broken_link_rejected(tmp_path: Path) -> None:
    stories = [
        {
            "id": "story:test",
            "type": "story",
            "title": "Тест",
            "year": 1936,
            "collection": "Сборник",
            "summary": "Краткое содержание.",
            "motifs": ["малахит"],
            "characters": ["char:missing"],
            "places": [],
        }
    ]
    (tmp_path / "stories.json").write_text(
        json.dumps(stories, ensure_ascii=False), encoding="utf-8"
    )
    (tmp_path / "characters.json").write_text("[]", encoding="utf-8")
    (tmp_path / "places.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="broken link"):
        BazhovStore.load(tmp_path)


def test_wrong_prefix_rejected(tmp_path: Path) -> None:
    (tmp_path / "stories.json").write_text("[]", encoding="utf-8")
    (tmp_path / "places.json").write_text("[]", encoding="utf-8")
    bad = json.dumps(
        [
            {
                "id": "place:should-be-char",
                "type": "character",
                "title": "Неправильный id",
                "aliases": [],
                "description": "Описание.",
                "stories": [],
            }
        ],
        ensure_ascii=False,
    )
    (tmp_path / "characters.json").write_text(bad, encoding="utf-8")
    with pytest.raises(ValueError, match="must start with"):
        BazhovStore.load(tmp_path)
