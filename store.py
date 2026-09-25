from __future__ import annotations

import json
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Iterator

DATA_DIR = Path(__file__).resolve().parent / "data"

_TYPE_FILES = {
    "story": "stories.json",
    "character": "characters.json",
    "place": "places.json",
}
_TYPE_PREFIXES = {"story": "story:", "character": "char:", "place": "place:"}
_LINK_FIELDS = {
    "story": ("characters", "places"),
    "character": ("stories",),
    "place": ("stories",),
}


def normalize(text: str) -> str:
    return text.lower().replace("ё", "е")


def _tokens(text: str) -> list[str]:
    return [t for t in normalize(text).split() if t]


class BazhovStore:
    def __init__(self, entities: dict[str, dict[str, Any]]) -> None:
        self.entities = entities

    @classmethod
    def load(cls, data_dir: Path | str = DATA_DIR) -> "BazhovStore":
        data_dir = Path(data_dir)
        entities: dict[str, dict[str, Any]] = {}
        for etype, filename in _TYPE_FILES.items():
            path = data_dir / filename
            if not path.exists():
                raise ValueError(f"missing data file: {path}")
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise ValueError(f"{path} must contain a JSON array")
            for ent in raw:
                cls._validate_entity(ent, etype, path)
                eid = ent["id"]
                if eid in entities:
                    raise ValueError(f"duplicate id {eid!r} in {path}")
                entities[eid] = ent
        for ent in entities.values():
            for field in _LINK_FIELDS[ent["type"]]:
                for link_id in ent[field]:
                    if link_id not in entities:
                        raise ValueError(
                            f"entity {ent['id']!r} has broken link {link_id!r} "
                            f"in field {field!r}"
                        )
        return cls(entities)

    @staticmethod
    def _validate_entity(ent: Any, etype: str, path: Path) -> None:
        if not isinstance(ent, dict):
            raise ValueError(f"{path}: entity must be a JSON object")
        eid = ent.get("id")
        prefix = _TYPE_PREFIXES[etype]
        if not isinstance(eid, str) or not eid.startswith(prefix):
            raise ValueError(f"{path}: id {eid!r} must start with {prefix!r}")
        if ent.get("type") != etype:
            raise ValueError(
                f"{path}: entity {eid!r} has type {ent.get('type')!r}, expected {etype!r}"
            )
        title = ent.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"{path}: entity {eid!r} needs a non-empty string 'title'")
        for field in _LINK_FIELDS[etype]:
            value = ent.get(field)
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ValueError(
                    f"{path}: entity {eid!r} field {field!r} must be a list of ids"
                )
        if etype == "story":
            year = ent.get("year")
            if not isinstance(year, int) or isinstance(year, bool):
                raise ValueError(f"{path}: story {eid!r} needs an integer 'year'")
            for field in ("collection", "summary"):
                value = ent.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{path}: story {eid!r} needs a string '{field}'")
            motifs = ent.get("motifs")
            if not isinstance(motifs, list) or not all(isinstance(m, str) for m in motifs):
                raise ValueError(f"{path}: story {eid!r} field 'motifs' must be a list of strings")
        else:
            description = ent.get("description")
            if not isinstance(description, str) or not description.strip():
                raise ValueError(
                    f"{path}: entity {eid!r} needs a non-empty string 'description'"
                )
            if etype == "character":
                aliases = ent.get("aliases")
                if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
                    raise ValueError(
                        f"{path}: character {eid!r} field 'aliases' must be a list of strings"
                    )
            else:
                prototype = ent.get("prototype")
                if not isinstance(prototype, str) or not prototype.strip():
                    raise ValueError(f"{path}: place {eid!r} needs a string 'prototype'")

    def _brief(self, ent: dict[str, Any]) -> dict[str, Any]:
        summary = (
            f"{ent['title']} ({ent['year']})"
            if ent["type"] == "story"
            else ent["title"]
        )
        return {
            "id": ent["id"],
            "title": ent["title"],
            "type": ent["type"],
            "summary": summary,
        }

    def _fields(self, ent: dict[str, Any], *, names_only: bool = False) -> Iterator[tuple[str, int]]:
        yield normalize(ent["title"]), 3
        if ent["type"] == "story":
            if not names_only:
                for motif in ent["motifs"]:
                    yield normalize(motif), 2
                yield normalize(ent["summary"]), 1
        elif ent["type"] == "character":
            for alias in ent["aliases"]:
                yield normalize(alias), 2
            if not names_only:
                yield normalize(ent["description"]), 1
        else:
            if not names_only:
                yield normalize(ent["prototype"]), 1
                yield normalize(ent["description"]), 1

    def _score(self, ent: dict[str, Any], tokens: list[str], *, names_only: bool = False) -> int:
        fields = list(self._fields(ent, names_only=names_only))
        score = 0
        for token in tokens:
            best = 0
            for value, weight in fields:
                if token == value:
                    best = max(best, weight + 1)
                elif token in value or value in token:
                    best = max(best, weight)
            score += best
        return score

    def _candidates(self, query: str, entity_type: str | None = None) -> list[dict[str, Any]]:
        names: dict[str, str] = {}
        for ent in self.entities.values():
            if entity_type and ent["type"] != entity_type:
                continue
            candidates_names = [ent["title"], *ent.get("aliases", [])]
            for name in candidates_names:
                names.setdefault(normalize(name), ent["id"])
        query_norm = normalize(query)
        close = get_close_matches(query_norm, list(names.keys()), n=10, cutoff=0.45)
        seen_ids: set[str] = set()
        for token in _tokens(query):
            close += [
                m for m in get_close_matches(token, list(names.keys()), n=5, cutoff=0.6)
                if names[m] not in seen_ids and m not in close
            ]
        result: list[dict[str, Any]] = []
        for name in close:
            eid = names[name]
            if eid in seen_ids:
                continue
            seen_ids.add(eid)
            result.append(self._brief(self.entities[eid]))
            if len(result) >= 5:
                break
        return result

    def resolve(self, query: str, entity_type: str | None = None) -> dict[str, Any]:
        self._check_type(entity_type)
        tokens = _tokens(query)
        if not tokens:
            raise ValueError("query must contain at least one word")
        scored = []
        for ent in self.entities.values():
            if entity_type and ent["type"] != entity_type:
                continue
            score = self._score(ent, tokens, names_only=True)
            if score > 0:
                scored.append((score, ent))
        scored.sort(key=lambda item: (-item[0], item[1]["title"]))
        results = [self._brief(ent) for _, ent in scored]
        candidates = self._candidates(query, entity_type) if not results else []
        return {"results": results, "candidates": candidates}

    def get(self, entity_id: str) -> dict[str, Any]:
        ent = self.entities.get(entity_id)
        if ent is None:
            raise ValueError(
                f"unknown id {entity_id!r}; use bazhov_resolve or bazhov_search first"
            )
        out = dict(ent)
        for field in _LINK_FIELDS[ent["type"]]:
            out[field] = [self._brief(self.entities[lid]) for lid in ent[field]]
        return out

    def search(
        self,
        keywords: str,
        entity_type: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> dict[str, Any]:
        self._check_type(entity_type)
        tokens = _tokens(keywords)
        if not tokens:
            raise ValueError("keywords must contain at least one word")
        scored = []
        for ent in self.entities.values():
            if entity_type and ent["type"] != entity_type:
                continue
            if year_from is not None or year_to is not None:
                if ent["type"] != "story":
                    continue
                if year_from is not None and ent["year"] < year_from:
                    continue
                if year_to is not None and ent["year"] > year_to:
                    continue
            score = self._score(ent, tokens)
            if score > 0:
                scored.append((score, ent))
        scored.sort(key=lambda item: (-item[0], item[1]["title"]))
        results = [self._brief(ent) for _, ent in scored]
        candidates = self._candidates(keywords, entity_type) if not results else []
        return {"results": results, "candidates": candidates}

    def context(self, theme: str) -> dict[str, Any]:
        found = self.search(theme)
        seed_ids = [item["id"] for item in found["results"]]
        if not seed_ids:
            seed_ids = [item["id"] for item in found["candidates"]]
        collected: dict[str, dict[str, Any]] = {}
        stories: dict[str, dict[str, Any]] = {}

        def add(eid: str) -> None:
            ent = self.entities[eid]
            collected[eid] = self._brief(ent)
            if ent["type"] == "story":
                stories[eid] = ent

        for seed_id in seed_ids:
            seed = self.entities[seed_id]
            add(seed_id)
            for field in _LINK_FIELDS[seed["type"]]:
                for link_id in seed[field]:
                    add(link_id)

        sorted_stories = sorted(stories.values(), key=lambda e: (e["year"], e["title"]))
        motifs: list[str] = []
        seen_motifs: set[str] = set()
        for story in sorted_stories:
            for motif in story["motifs"]:
                if motif not in seen_motifs:
                    seen_motifs.add(motif)
                    motifs.append(motif)
        return {
            "characters": [b for b in collected.values() if b["type"] == "character"],
            "places": [b for b in collected.values() if b["type"] == "place"],
            "stories": [self._brief(s) for s in sorted_stories],
            "years": sorted({s["year"] for s in stories.values()}),
            "motifs": motifs,
        }

    @staticmethod
    def _check_type(entity_type: str | None) -> None:
        if entity_type is not None and entity_type not in _TYPE_FILES:
            raise ValueError(
                f"entity_type must be one of {sorted(_TYPE_FILES)}, got {entity_type!r}"
            )
