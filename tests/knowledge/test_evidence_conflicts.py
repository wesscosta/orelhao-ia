from datetime import date

from orelhao.services.knowledge.evidence_conflicts import conflicting_facts
from orelhao.services.knowledge.models import Chunk, SearchResult


def item(cid: str, value: str, **metadata: str) -> SearchResult:
    return SearchResult(Chunk(cid, "d", "Uma informação.", "source.md", 0, {
        "entity_id": "curso:excel", "fact_key": "price", "fact_value": value,
        "authority": "primary", **metadata
    }), 0.8)


def test_same_scoped_fact_conflict() -> None:
    x = conflicting_facts([item("a","R$ 100"), item("b","R$ 200")], as_of=date(2026, 10, 29))
    assert len(x) == 1
    assert x[0].chunk_ids == ("a", "b")


def test_non_overlapping_and_unit_specific_facts_do_not_conflict() -> None:
    a = item("a", "R$ 100", valid_until="2026-08-01")
    b = item("b", "R$ 200", valid_from="2026-10-01")
    assert not conflicting_facts([a,b], as_of=date(2026, 10, 29))
    c = item("c", "R$ 100", unit_id="Teresina")
    d = item("d", "R$ 200", unit_id="Parnaiba")
    assert not conflicting_facts([c,d], as_of=date(2026, 10, 29))
