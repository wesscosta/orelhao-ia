from datetime import date

from orelhao.services.knowledge.query_constraints import parse_query_constraints
from orelhao.services.knowledge.source_policy import (
    current_state_is_verified,
    parse_date,
    source_matches,
)


def test_query_constraints_stable_vs_current() -> None:
    today = date(2026, 10, 29)
    current = parse_query_constraints("Há vagas disponíveis hoje?", as_of=today)
    historical = parse_query_constraints("Quais editais apareciam em agosto de 2026?", as_of=today)
    assert current.requires_current_state
    assert not historical.requires_current_state
    assert current.attribute == "availability"


def test_unit_constraints_without_confusing_an_unrelated_unit() -> None:
    q = parse_query_constraints("Qual é o telefone da unidade de Parnaíba?", as_of=date(2026,10,29))
    assert q.unit_id == "parnaiba"
    assert not source_matches({"unit_id": "Teresina"}, q)
    assert source_matches({"unit_id": "Parnaíba"}, q)


def test_validity_metadata_is_not_same_as_retrieval_date() -> None:
    q = parse_query_constraints("Ainda existem vagas hoje?", as_of=date(2026,10,29))
    assert not current_state_is_verified({"retrieved_at": "2026-10-29"}, q, as_of=date(2026,10,29))
    assert parse_date("2026-10-29") == date(2026,10,29)
    assert parse_date("not-a-date") is None



def test_self_declared_current_data_needs_authoritative_origin() -> None:
    today = date(2026,10,29)
    q = parse_query_constraints("Ainda há vagas hoje?", as_of=today)
    metadata = {"current_state_confirmed": True, "verified_at": "2026-10-29",
                "valid_until": "2026-10-29"}
    assert not current_state_is_verified(metadata, q, as_of=today)
    metadata.update({"authority": "primary", "source_url": "https://example.org/fonte"})
    assert current_state_is_verified(metadata, q, as_of=today)
