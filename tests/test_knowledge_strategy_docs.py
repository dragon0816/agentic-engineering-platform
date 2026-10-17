"""The Knowledge Strategy v1.2 contract files agree with each other.

BI Schema v0, the 25-question benchmark draft and the Knowledge API mock data are
documentation, but the Atlas Coding Agent builds against the mock files without a
running AEP. A mock that drifts from its JSON Schema, or a benchmark triple that
names a relationship the schema does not allow, would be found only when Atlas
breaks. The repository has no JSON Schema library, so a small validator below
covers the subset of JSON Schema 2020-12 these files use.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BI_SCHEMA = ROOT / "docs/proposals/bi_schema_v0/bi_schema_v0.json"
BENCHMARK = ROOT / "docs/proposals/knowledge_benchmark_v0/questions.json"
API = ROOT / "docs/contracts/knowledge-api"
SCHEMAS = API / "schemas"
MOCKS = API / "mock"

_TYPES: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(ref: str, base: Path, doc: Any) -> tuple[Any, Path, Any]:
    file_part, _, pointer = ref.partition("#")
    if file_part:
        base = base.parent / file_part
        doc = load(base)
    node = doc
    for part in [p for p in pointer.split("/") if p]:
        node = node[part]
    return node, base, doc


def _type_ok(value: Any, name: str) -> bool:
    if name == "null":
        return value is None
    if name in ("integer", "number") and isinstance(value, bool):
        return False
    if name == "integer" and isinstance(value, float):
        return value.is_integer()
    return isinstance(value, _TYPES[name])


def errors(value: Any, schema: Any, base: Path, doc: Any, where: str = "$") -> list[str]:
    """Errors of `value` against `schema` (subset of JSON Schema 2020-12)."""
    if schema is True or schema == {}:
        return []
    if "$ref" in schema:
        target, tbase, tdoc = _resolve(schema["$ref"], base, doc)
        return errors(value, target, tbase, tdoc, where)
    if "anyOf" in schema:
        options = [errors(value, option, base, doc, where) for option in schema["anyOf"]]
        return [] if any(not found for found in options) else [f"{where}: matches no anyOf option"]
    found: list[str] = []
    if "const" in schema and value != schema["const"]:
        found.append(f"{where}: {value!r} != const {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        found.append(f"{where}: {value!r} not in enum")
    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(value, name) for name in names):
            return found + [f"{where}: {type(value).__name__} is not {names}"]
    if isinstance(value, str):
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            found.append(f"{where}: {value!r} does not match {schema['pattern']}")
        if len(value) < schema.get("minLength", 0):
            found.append(f"{where}: shorter than minLength")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            found.append(f"{where}: below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            found.append(f"{where}: above maximum")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            found.append(f"{where}: fewer than minItems")
        if "items" in schema:
            for index, item in enumerate(value):
                found += errors(item, schema["items"], base, doc, f"{where}[{index}]")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                found.append(f"{where}: missing {key}")
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                found += errors(item, properties[key], base, doc, f"{where}.{key}")
            elif extra is False:
                found.append(f"{where}: unexpected {key}")
            elif isinstance(extra, dict):
                found += errors(item, extra, base, doc, f"{where}.{key}")
    return found


def check(value: Any, ref: str) -> list[str]:
    """Validate against `file.schema.json` or `file.schema.json#/$defs/Name` in SCHEMAS."""
    file_part, _, pointer = ref.partition("#")
    base = SCHEMAS / file_part
    doc = load(base)
    return errors(value, {"$ref": "#" + pointer} if pointer else doc, base, doc)


def test_validator_rejects_what_it_should() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["a"],
        "properties": {"a": {"type": "integer", "minimum": 1}, "b": {"enum": ["x"]}},
    }
    assert errors({"a": 1, "b": "x"}, schema, SCHEMAS / "x", {}) == []
    assert errors({"a": 0, "b": "y", "c": 1}, schema, SCHEMAS / "x", {}) != []
    assert errors({}, schema, SCHEMAS / "x", {}) == ["$: missing a"]
    assert errors(True, {"type": "integer"}, SCHEMAS / "x", {}) != []


def test_every_new_json_file_parses() -> None:
    files = [BI_SCHEMA, BENCHMARK, *sorted(SCHEMAS.glob("*.json")), *sorted(MOCKS.glob("*.json"))]
    assert len(files) > 20
    for path in files:
        load(path)


MOCK_INDEX = load(MOCKS / "index.json")["files"]


@pytest.mark.parametrize("entry", MOCK_INDEX, ids=[entry["file"] for entry in MOCK_INDEX])
def test_mock_matches_its_schema(entry: dict[str, Any]) -> None:
    payload = load(MOCKS / entry["file"])
    assert check(payload, "envelope.schema.json") == []
    assert (payload["data"] is None) != (payload["error"] is None), "exactly one of data and error"
    assert payload["source"]["synthetic"] is True
    if entry["data_schema"] is None:
        assert payload["error"]["http_status"] == entry["http_status"]
    else:
        assert entry["http_status"] == 200
        assert check(payload["data"], entry["data_schema"]) == []


def test_openapi_references_existing_files() -> None:
    text = (API / "openapi.yaml").read_text(encoding="utf-8")
    assert text.startswith("openapi: 3.1.0")
    refs = set(re.findall(r"\./((?:schemas|mock)/[A-Za-z0-9_.]+\.json)(?:#/\$defs/(\w+))?", text))
    assert refs
    for path, name in refs:
        assert (API / path).is_file(), path
        if name:
            assert name in load(API / path)["$defs"], (path, name)
    indexed = {entry["file"] for entry in MOCK_INDEX}
    assert indexed == {path.name for path in MOCKS.glob("*.json")} - {"index.json"}


def _entities() -> dict[str, dict[str, Any]]:
    data = load(MOCKS / "entities.json")["data"]
    return {f"{e['entity_type']}:{e['canonical_key']}": e for e in data}


def _relationships() -> list[dict[str, Any]]:
    return list(load(MOCKS / "relationships.json")["data"])


def _source(rel_type: dict[str, Any], subject_type: str) -> dict[str, Any] | None:
    """The (domain, origin) entry of a relationship type for this subject type."""
    for source in rel_type["sources"]:
        if source["domain"] == subject_type:
            return dict(source)
    return None


def _in_range(rel_type: dict[str, Any], object_type: str) -> bool:
    allowed = rel_type["range"]
    return object_type in (allowed if isinstance(allowed, list) else [allowed])


def _matches(pattern: str, value: str) -> bool:
    return value.startswith(pattern[:-1]) if pattern.endswith("*") else value == pattern


def test_mock_graph_obeys_bi_schema_v0() -> None:
    schema = load(BI_SCHEMA)
    assert schema["schema_id"] == "bi.schema/v0"
    types = schema["entity_types"]
    entities = _entities()
    for ref, entity in entities.items():
        spec = types[entity["entity_type"]]
        found = errors(entity["properties"], spec["properties_schema"], BI_SCHEMA, schema)
        assert found == [], (ref, found)
    keys = {(e["entity_type"], e["canonical_key"]) for e in entities.values()}
    accounts = {key for kind, key in keys if kind == "Account"}
    assert accounts.isdisjoint({key for kind, key in keys if kind == "Ecosystem"})

    by_id = {e["entity_id"]: e for e in entities.values()}
    rel_types = {t["name"]: t for t in schema["relationship_types"]}
    vendors: dict[str, int] = {}
    for rel in _relationships():
        spec = rel_types[rel["relationship_type"]]
        subject, obj = by_id[rel["subject_entity_id"]], by_id[rel["object_entity_id"]]
        source = _source(spec, subject["entity_type"])
        assert source is not None, rel
        assert _in_range(spec, obj["entity_type"]), rel
        assert rel["origin"] == source["origin"]
        if rel["relationship_type"] == "vendor":
            vendors[subject["entity_id"]] = vendors.get(subject["entity_id"], 0) + 1
        if rel["relationship_type"] == "competing_solutions":
            assert subject["properties"]["is_own_solution"] is True, rel
            assert obj["properties"]["is_own_solution"] is False, rel
    # Slide 8: our solutions have no vendor; a competitor's has exactly one.
    for entity in entities.values():
        if entity["entity_type"] == "TestSolution":
            expected = 0 if entity["properties"]["is_own_solution"] else 1
            assert vendors.get(entity["entity_id"], 0) == expected, entity["entity_id"]
    origins = {s["origin"] for t in schema["relationship_types"] for s in t["sources"]}
    assert origins <= {"source-bi-doc", "source-v1.0", "proposed-v0"}
    assert all(t["origin"] == "source-bi-doc" for t in types.values())


def test_claims_keep_assertion_inference_and_review_apart() -> None:
    evidence_ids = {e["evidence_id"] for e in load(MOCKS / "evidence.json")["data"]}
    detail = load(MOCKS / "entity_detail.json")["data"]
    claims = detail["claims"]
    assert claims
    for claim in claims:
        assert {e["evidence_id"] for e in claim["evidence"]} <= evidence_ids
    for rel in _relationships():
        for summary in rel["claims"]:
            if summary["claim_kind"] == "inference":
                assert summary["verification_status"] != "verified", rel
                assert rel["graph_state"] == "missing/inferred"
            if summary["verification_status"] == "disputed":
                assert rel["graph_state"] == "conflict/disputed"
        assert rel["evidence_ids"], rel


def test_stale_cards_follow_the_90_day_rule() -> None:
    entities = _entities()
    stale = {ref for ref, e in entities.items() if e["stale"]}
    assert stale, "the mock should exercise the stale rule"
    nodes = {n["id"]: n for n in load(MOCKS / "graph.json")["data"]["nodes"]}
    for ref in stale:
        assert nodes[entities[ref]["entity_id"]]["state"] in ("stale", "conflict/disputed")


def test_metadata_scope_hides_content() -> None:
    schema = load(BI_SCHEMA)
    for entity in load(MOCKS / "entities.metadata.json")["data"]:
        sensitive = schema["entity_types"][entity["entity_type"]]["label_is_content"] or entity[
            "classification"
        ] in ("CONFIDENTIAL", "RESTRICTED")
        assert entity["display_name_redacted"] is sensitive
        assert (entity["display_name"] is None) is sensitive
    for document in load(MOCKS / "documents.json")["data"]:
        assert document["title"] is None and document["original_ref"] is None
    assert load(MOCKS / "evidence_detail.metadata.json")["data"]["text"] is None
    for node in load(MOCKS / "graph.json")["data"]["nodes"]:
        if node["type"] in ("Account", "CustomerProduct", "Opportunity"):
            assert node["label_redacted"] is True


def test_benchmark_draft_is_consistent_and_marked_unreviewed() -> None:
    bench = load(BENCHMARK)
    questions = bench["questions"]
    assert len(questions) == 25
    assert bench["ground_truth_status"] == "draft-unreviewed"
    assert bench["benchmark_owner"] == "owner" and bench["formal_reviewers"] == []
    categories = [c["id"] for c in bench["categories"]]
    assert len(categories) == 5
    for category in categories:
        assert sum(1 for q in questions if q["category"] == category) == 5
    assert len({q["id"] for q in questions}) == 25

    schema = load(BI_SCHEMA)
    rel_types = {t["name"]: t for t in schema["relationship_types"]}
    entities = _entities()
    present = {
        (r["subject_entity_id"], r["relationship_type"], r["object_entity_id"])
        for r in _relationships()
    }
    required = {
        "question",
        "expected_entities",
        "expected_relationships",
        "evidence_requirements",
        "expected_answer",
        "review_domain",
    }
    for q in questions:
        assert required <= set(q), q["id"]
        assert q["review_status"] == "draft-unreviewed" and q["reviewer"] is None
        assert q["review_domain"] in ("BD", "PM", "AE")
        for ref in q["expected_entities"]:
            assert ref in entities, (q["id"], ref)
        for triple in q["expected_relationships"]:
            subject, obj = entities[triple["subject"]], entities[triple["object"]]
            spec = rel_types[triple["relationship"]]
            assert _source(spec, subject["entity_type"]) is not None, (q["id"], triple)
            assert _in_range(spec, obj["entity_type"]), (q["id"], triple)
            key = (subject["entity_id"], triple["relationship"], obj["entity_id"])
            assert key in present, (q["id"], triple)
        by_id = {e["entity_id"]: ref for ref, e in entities.items()}
        for triple in q.get("expected_absent_relationships", []):
            assert not any(
                _matches(triple["subject"], by_id[s])
                and r == triple["relationship"]
                and _matches(triple["object"], by_id[o])
                for s, r, o in present
            ), (q["id"], triple)
