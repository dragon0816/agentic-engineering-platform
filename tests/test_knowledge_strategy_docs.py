"""The Knowledge Strategy contract files (v1.2, revised by v1.3) agree with each other.

BI Schema v1, the 25-question benchmark draft and the Knowledge API mock data are
documentation, but the Atlas Coding Agent builds against the mock files without a
running AEP. A mock that drifts from its JSON Schema, or a benchmark triple that
names a relationship the schema does not allow, would be found only when Atlas
breaks. The repository has no JSON Schema library, so a small validator below
covers the subset of JSON Schema 2020-12 these files use.

v1.3 (2026-10-19) moved the mock and the benchmark from BI Schema v0 (built from the
BI slides) to v1 (built from the owner's bi_schema.py, committed as test data under
tests/fixtures/bi_vault_example). v0 is kept unchanged for history; its checks here
are that it is unchanged and that its upcast to v1 covers every v0 name.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BI_SCHEMA_V0 = ROOT / "docs/proposals/bi_schema_v0/bi_schema_v0.json"
# sha256 of the committed (LF) bytes; checkouts may convert to CRLF, so hashes normalize.
BI_SCHEMA_V0_SHA256 = "ccb98e583503bae330b7e66e1b3c7c03416c323e5f0d5dfd579603e6ba23b3de"
BI_SCHEMA = ROOT / "docs/proposals/bi_schema_v1/bi_schema_v1.json"
BENCHMARK = ROOT / "docs/proposals/knowledge_benchmark_v0/questions.json"
VAULT_QUESTIONS = ROOT / "docs/proposals/knowledge_benchmark_v0/vault_example_questions.json"
FIXTURE = ROOT / "tests/fixtures/bi_vault_example"
BI_SCHEMA_PY = FIXTURE / "tools/bi_schema.py"
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


def sha256_lf(path: Path) -> str:
    """sha256 with CRLF normalized to LF: the same on Windows and Linux checkouts."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


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
    files = [
        BI_SCHEMA_V0,
        BI_SCHEMA,
        BENCHMARK,
        VAULT_QUESTIONS,
        *sorted(SCHEMAS.glob("*.json")),
        *sorted(MOCKS.glob("*.json")),
    ]
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


def test_bi_schema_v0_is_kept_for_history() -> None:
    assert sha256_lf(BI_SCHEMA_V0) == BI_SCHEMA_V0_SHA256
    schema = load(BI_SCHEMA_V0)
    assert schema["schema_id"] == "bi.schema/v0"
    origins = {s["origin"] for t in schema["relationship_types"] for s in t["sources"]}
    assert origins <= {"source-bi-doc", "source-v1.0", "proposed-v0"}
    assert all(t["origin"] == "source-bi-doc" for t in schema["entity_types"].values())


def test_v0_to_v1_upcast_covers_every_v0_name() -> None:
    v0, v1 = load(BI_SCHEMA_V0), load(BI_SCHEMA)
    upcast = v1["upcast_from_v0"]
    assert upcast["from"] == "bi.schema/v0" and upcast["to"] == "bi.schema/v1"
    assert set(upcast["type_map"]) == set(v0["entity_types"])
    assert set(upcast["type_map"].values()) == set(v1["entity_types"])
    for name, spec in v0["entity_types"].items():
        assert set(spec["properties_schema"]["properties"]) == set(upcast["property_map"][name])
        v1_props = v1["entity_types"][name]["properties_schema"]["properties"]
        for rule in upcast["property_map"][name].values():
            assert rule["to"] is None or rule["to"] in v1_props, (name, rule)
    v0_pairs = {(s["domain"], t["name"]) for t in v0["relationship_types"] for s in t["sources"]}
    mapped = {(r["domain"], r["from"]): r["to"] for r in upcast["relationship_map"]}
    assert set(mapped) == v0_pairs
    v1_rel = {t["name"]: t for t in v1["relationship_types"]}
    for (domain, _), target in mapped.items():
        assert _source(v1_rel[target], domain) is not None, (domain, target)
    assert set(upcast["record_map"]) == set(v0["entity_record"]["properties"]) - set(
        v1["entity_record"]["properties"]
    ) | {"updated"}


def _code_line(ref: str) -> str:
    match = re.fullmatch(r"bi_schema\.py:(\d+)", ref)
    assert match, ref
    return BI_SCHEMA_PY.read_text(encoding="utf-8").splitlines()[int(match.group(1)) - 1]


def test_bi_schema_v1_traces_every_name_to_bi_schema_py() -> None:
    """Each source-bi-schema-py name points at the bi_schema.py line that defines it."""
    schema = load(BI_SCHEMA)
    assert schema["schema_id"] == "bi.schema/v1"
    assert sha256_lf(BI_SCHEMA_PY) == schema["source"]["primary_sha256"]
    types = schema["entity_types"]
    assert [t for t, s in types.items() if s["origin"] == "proposed"] == ["Opportunity"]
    for name, spec in types.items():
        if spec["origin"] == "proposed":
            assert spec["reason"] and spec["code_ref"] is None
            continue
        assert spec["origin"] == "source-bi-schema-py"
        assert f'"{spec["code_key"]}": schema("{spec["folder"]}"' in _code_line(spec["code_ref"])
        naming = spec["naming_field"]
        assert f'("{naming["field"]}", F(' in _code_line(naming["code_ref"])
        assert naming["field"] == {"Signal": "title", "CustomerProduct": "product_name"}.get(
            name, "name"
        )
        assert spec["has_confidence_and_updated"] is (name not in ("Account", "Node", "Signal"))
        for prop, prop_spec in spec["properties_schema"]["properties"].items():
            assert prop_spec["x-field-class"] in ("sourced", "judgement", "derived"), (name, prop)
            if prop_spec["x-origin"] == "proposed":
                assert prop_spec["x-reason"], (name, prop)
                continue
            line = _code_line(prop_spec["x-code"])
            assert f'("{prop}", F(' in line or f'f["{prop}"] = F(' in line, (name, prop, line)
            assert f'F("{prop_spec["x-kind"]}"' in line, (name, prop)
        assert (
            "confidence" in spec["properties_schema"]["properties"]
            or not spec["has_confidence_and_updated"]
        )
    for rel in schema["relationship_types"]:
        for source in rel["sources"]:
            if source["origin"] == "proposed":
                assert source["reason"] and source["code_ref"] is None, rel["name"]
                continue
            assert source["origin"] == "source-bi-schema-py"
            line = _code_line(source["code_ref"])
            assert f'("{rel["name"]}", F("{source["code_kind"]}"' in line, (rel["name"], line)
            assert source["cardinality"] == ("one" if source["code_kind"] == "link" else "many")
    proposed_rels = {
        (s["domain"], t["name"])
        for t in schema["relationship_types"]
        for s in t["sources"]
        if s["origin"] == "proposed"
    }
    assert proposed_rels == {
        ("Opportunity", "account"),
        ("Opportunity", "test_solutions"),
        ("Opportunity", "customer_product"),
        ("TestSolution", "competing_vendors"),
    }
    reference = types["Node"]["properties_schema"]["properties"]["reference_position"]["enum"]
    assert sorted(reference) == sorted(p.stem for p in (FIXTURE / "BI/Node").glob("*.md"))


def test_mock_graph_obeys_bi_schema_v1() -> None:
    schema = load(BI_SCHEMA)
    types = schema["entity_types"]
    entities = _entities()
    for ref, entity in entities.items():
        assert entity["schema_id"] == "bi.schema/v1", ref
        spec = types[entity["entity_type"]]
        found = errors(entity["properties"], spec["properties_schema"], BI_SCHEMA, schema)
        assert found == [], (ref, found)
        for field in spec["x-defaults"]:
            assert field in entity["properties"], (ref, field)
        if entity["entity_type"] == "Node":
            properties = entity["properties"]
            has_reference = "reference_position" in properties
            assert has_reference is (properties["position_set"] == "vault-reference"), ref
    keys = {(e["entity_type"], e["canonical_key"]) for e in entities.values()}
    accounts = {key for kind, key in keys if kind == "Account"}
    assert accounts.isdisjoint({key for kind, key in keys if kind == "Ecosystem"})
    reference_nodes = {
        e["properties"].get("reference_position")
        for e in entities.values()
        if e["entity_type"] == "Node"
    }
    assert reference_nodes - {None} == set(
        types["Node"]["properties_schema"]["properties"]["reference_position"]["enum"]
    )

    by_id = {e["entity_id"]: e for e in entities.values()}
    rel_types = {t["name"]: t for t in schema["relationship_types"]}
    vendors: dict[str, int] = {}
    single: dict[tuple[str, str], int] = {}
    for rel in _relationships():
        spec = rel_types[rel["relationship_type"]]
        subject, obj = by_id[rel["subject_entity_id"]], by_id[rel["object_entity_id"]]
        source = _source(spec, subject["entity_type"])
        assert source is not None, rel
        assert _in_range(spec, obj["entity_type"]), rel
        assert rel["origin"] == source["origin"]
        assert rel["provenance"]["schema_id"] == "bi.schema/v1"
        if source["cardinality"] == "one":
            key = (subject["entity_id"], rel["relationship_type"])
            single[key] = single.get(key, 0) + 1
        if rel["relationship_type"] == "vendor":
            vendors[subject["entity_id"]] = vendors.get(subject["entity_id"], 0) + 1
        if rel["relationship_type"] in ("competing_solutions", "competing_vendors"):
            assert subject["properties"]["is_own_solution"] is True, rel
        if rel["relationship_type"] == "competing_solutions":
            assert obj["properties"]["is_own_solution"] is False, rel
    assert all(count == 1 for count in single.values()), single
    # bi_schema.py:37 / tools README: our solutions have no vendor; a competitor's has one.
    for entity in entities.values():
        if entity["entity_type"] == "TestSolution":
            expected = 0 if entity["properties"]["is_own_solution"] else 1
            assert vendors.get(entity["entity_id"], 0) == expected, entity["entity_id"]
    used = {r["relationship_type"] for r in _relationships()}
    assert "competing_vendors" in used, "the mock should exercise the type-check rule"
    graph = load(MOCKS / "graph.json")["data"]
    assert {n["id"] for n in graph["nodes"]} == set(by_id)
    assert {(e["id"], e["type"]) for e in graph["edges"]} == {
        (r["relationship_id"], r["relationship_type"]) for r in _relationships()
    }


def test_judgement_fields_carry_field_provenance() -> None:
    """ADR-K11: every judgement value says who set it, when, how and (if a person) why."""
    schema = load(BI_SCHEMA)
    for name, entity in [
        *_entities().items(),
        *((e["entity_id"], e) for e in load(MOCKS / "entities.metadata.json")["data"]),
    ]:
        props = schema["entity_types"][entity["entity_type"]]["properties_schema"]["properties"]
        provenance = entity["field_provenance"]
        assert set(provenance) <= set(entity["properties"]), name
        for field in entity["properties"]:
            if props[field]["x-field-class"] == "judgement":
                assert field in provenance, (name, field)
        for field, item in provenance.items():
            assert item["version"] <= entity["record_version"], (name, field)
            if item["origin"] == "human" and not item["reason_redacted"]:
                assert item["reason"], (name, field)
    for entity in load(MOCKS / "entities.metadata.json")["data"]:
        assert all(p["reason"] is None for p in entity["field_provenance"].values())
    humans = [
        e
        for e in _entities().values()
        if e["field_provenance"].get("priority", {}).get("origin") == "human"
    ]
    assert humans, "the mock should exercise a human-set judgement field"


def test_entity_history_never_lets_an_import_overwrite_a_person() -> None:
    history = load(MOCKS / "entity_history.json")["data"]
    entity = next(e for e in _entities().values() if e["entity_id"] == history["entity_id"])
    assert history["record_version"] == entity["record_version"]
    changes = [c for c in history["changes"] if c["field"] == "priority"]
    accepted = [c for c in changes if c["status"] == "accepted"]
    assert accepted[-1]["new_value"] == entity["properties"]["priority"]
    current = entity["field_provenance"]["priority"]
    assert (current["origin"], current["set_by"], current["version"]) == (
        accepted[-1]["origin"],
        accepted[-1]["set_by"],
        accepted[-1]["version"],
    )
    for before, after in zip(accepted, accepted[1:], strict=False):
        assert (
            after["old_value"] == before["new_value"] and after["base_version"] == before["version"]
        )
    for change in changes:
        if change["status"] == "rejected_stale_base":
            newer = [c for c in accepted if c["set_at"] < change["set_at"]]
            assert change["base_version"] < newer[-1]["version"]
            assert change["version"] is None
        if change["status"] == "pending_review" and change["origin"] in ("import", "agent"):
            assert current["origin"] == "human" and change["version"] is None
            assert change["new_value"] != entity["properties"]["priority"]
    assert any(c["status"] == "pending_review" and c["origin"] == "import" for c in changes)


def test_strategy_config_pins_schema_v1_digest() -> None:
    digest = "sha256:" + sha256_lf(BI_SCHEMA)
    for strategy in load(MOCKS / "strategies.json")["data"]:
        if strategy["schema"] is not None:
            assert strategy["schema"]["schema_id"] == "bi.schema/v1"
            assert strategy["schema"]["digest"] == digest, strategy["strategy_id"]


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
    assert bench["schema_id"] == "bi.schema/v1"

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


def test_supplemental_question_matches_the_history_mock() -> None:
    bench = load(BENCHMARK)
    supplemental = bench["supplemental_questions"]
    assert [q["id"] for q in supplemental] == ["SUP-01"]
    assert all(q["id"] not in {x["id"] for x in bench["questions"]} for q in supplemental)
    entities = _entities()
    present = {
        (r["subject_entity_id"], r["relationship_type"], r["object_entity_id"])
        for r in _relationships()
    }
    history = load(MOCKS / "entity_history.json")["data"]
    for q in supplemental:
        assert q["review_status"] == "draft-unreviewed" and q["reviewer"] is None
        for ref in q["expected_entities"]:
            assert ref in entities, ref
        for triple in q["expected_relationships"]:
            key = (
                entities[triple["subject"]]["entity_id"],
                triple["relationship"],
                entities[triple["object"]]["entity_id"],
            )
            assert key in present, triple
        expected = q["expected_field_history"]
        entity = entities[expected["entity"]]
        assert history["entity_id"] == entity["entity_id"]
        assert entity["properties"][expected["field"]] == expected["current_value"]
        current = entity["field_provenance"][expected["field"]]
        assert (current["origin"], current["set_by"]) == (
            expected["current_origin"],
            expected["current_set_by"],
        )
        by_status = {c["status"]: c for c in history["changes"] if c["field"] == expected["field"]}
        assert by_status["rejected_stale_base"]["new_value"] == expected["rejected_stale_value"]
        assert by_status["pending_review"]["new_value"] == expected["pending_import_value"]


def _card(ref: str) -> Path:
    folder, _, stem = ref.partition(":")
    return FIXTURE / "BI" / folder / f"{stem}.md"


def _frontmatter_links(path: Path) -> dict[str, list[str]]:
    """Frontmatter key -> wikilink targets, for the inline and block list forms the vault uses."""
    text = path.read_text(encoding="utf-8")
    block = text.split("---", 2)[1]
    links: dict[str, list[str]] = {}
    key = ""
    for line in block.splitlines():
        match = re.match(r"^([a-z_]+):(.*)$", line)
        if match:
            key = match.group(1)
            links[key] = re.findall(r"\[\[([^\]|]+)", match.group(2))
        elif line.startswith("  - ") and key:
            links[key] += re.findall(r"\[\[([^\]|]+)", line)
    return links


def test_vault_example_questions_are_grounded_in_the_fixture() -> None:
    bench = load(VAULT_QUESTIONS)
    questions = bench["questions"]
    assert len(questions) == 8 and len({q["id"] for q in questions}) == 8
    assert bench["ground_truth_status"] == "draft-unreviewed" and bench["formal_reviewers"] == []
    assert bench["schema_id"] == "bi.schema/v1"
    assert not {q["id"] for q in questions} & {q["id"] for q in load(BENCHMARK)["questions"]}
    rel_types = {t["name"]: t for t in load(BI_SCHEMA)["relationship_types"]}
    for q in questions:
        assert q["review_status"] == "draft-unreviewed" and q["reviewer"] is None, q["id"]
        assert q["corpus"] == "vault_example"
        for ref in q["expected_entities"]:
            assert _card(ref).is_file(), (q["id"], ref)
        for ref in q.get("expected_absent_cards", []):
            assert not _card(ref).exists(), (q["id"], ref)
        for triple in q["expected_relationships"]:
            subject_type = triple["subject"].split(":")[0]
            object_type = triple["object"].split(":")[0]
            spec = rel_types[triple["relationship"]]
            assert _source(spec, subject_type) is not None, (q["id"], triple)
            assert _in_range(spec, object_type), (q["id"], triple)
            field = triple.get("source_field", triple["relationship"])
            target = triple["object"].split(":", 1)[1]
            assert target in _frontmatter_links(_card(triple["subject"])).get(field, []), (
                q["id"],
                triple,
            )
        for triple in q["expected_absent_relationships"]:
            if "*" in triple["subject"]:
                folder = triple["subject"].split(":")[0]
                subjects = sorted((FIXTURE / "BI" / folder).glob("*.md"))
            else:
                subjects = [_card(triple["subject"])]
            for subject in subjects:
                targets = _frontmatter_links(subject).get(triple["relationship"], [])
                obj = triple["object"].split(":", 1)[1]
                if obj == "*":
                    folder = triple["object"].split(":")[0]
                    hits = [t for t in targets if (FIXTURE / "BI" / folder / f"{t}.md").is_file()]
                else:
                    hits = [t for t in targets if t == obj]
                assert hits == [], (q["id"], subject.name, triple)
