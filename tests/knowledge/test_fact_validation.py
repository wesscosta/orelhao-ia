"""Fact Validator PR-03: contratos determinísticos, negações de escopo e corpus real."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from orelhao.services.knowledge.fact_extraction import (
    FactKind,
    extract_explicit_facts,
)
from orelhao.services.knowledge.fact_validation import (
    FactStatus,
    validate_claim_facts,
)
from orelhao.services.knowledge.loader import load_documents
from orelhao.services.knowledge.models import Chunk, SearchResult

TODAY = date(2026, 10, 29)
SOURCES = Path(__file__).resolve().parents[2] / "knowledge" / "sources"


def evidence(text: str, **metadata: object) -> SearchResult:
    base: dict[str, object] = {
        "authority": "primary", "source_url": "https://example.org/oficial",
    }
    base.update(metadata)
    return SearchResult(
        Chunk("test:0", "test", text, "source.md", 0, base), 0.88,
    )


def official_source(path: str) -> SearchResult:
    document = next(
        x for x in load_documents(SOURCES) if x.source == path
    )
    return SearchResult(
        Chunk(path + ":0", document.id, document.text, path, 0, document.metadata),
        0.84,
    )


def check(claim: str, sources: list[SearchResult], **opts: object) -> FactStatus:
    return validate_claim_facts(claim, sources, as_of=TODAY, **opts).status


def test_prices_and_phone_normalize_without_float_rounding() -> None:
    atoms = extract_explicit_facts("Preço: R$ 1.234,56. Contato +55 (86) 3228-9500.")
    assert [(a.kind, a.value, a.unit) for a in atoms] == [
        (FactKind.PRICE, "1234.56", "BRL"),
        (FactKind.PHONE, "8632289500", "br_phone"),
    ]
    text = "Preço R$ 242,00; telefone (86) 3228-9500."
    assert check(
        "Custa R$ 242,00.", [evidence(text)],
    ) == FactStatus.VALUE_MATCH
    assert check(
        "Custa R$ 243,00.", [evidence(text)],
    ) == FactStatus.VALUE_MISMATCH
    assert check(
        "O telefone é (86) 3228-9501.", [evidence(text)],
    ) == FactStatus.VALUE_MISMATCH


def test_working_days_not_equal_calendar_days_or_unspecified() -> None:
    source = evidence("Prazo: até 15 dias úteis, prorrogável por mais 15 dias.")
    assert check("O prazo é de 15 dias úteis.", [source]) == FactStatus.VALUE_MATCH
    assert check("O prazo é de 15 dias corridos.", [source]) == FactStatus.VALUE_MISMATCH
    assert check("O prazo é de 15 dias.", [source]) == FactStatus.NO_ADMISSIBLE_SOURCE
    assert check("Pode prorrogar por mais 15 dias.", [source]) == FactStatus.VALUE_MATCH
    assert check("Pode prorrogar por mais 10 dias.", [source]) == FactStatus.VALUE_MISMATCH


def test_age_distinguishes_course_duration_and_dates() -> None:
    source = evidence("Curso de Excel: 30 horas. Idade mínima de 14 anos.")
    assert check("O curso dura 30 horas.", [source]) == FactStatus.VALUE_MATCH
    assert check("O curso dura 40 horas.", [source]) == FactStatus.VALUE_MISMATCH
    assert check("A idade mínima é 14 anos.", [source]) == FactStatus.VALUE_MATCH
    assert check("A idade mínima é 12 anos.", [source]) == FactStatus.VALUE_MISMATCH
    assert not extract_explicit_facts("O ano é 2026.")
    assert not extract_explicit_facts("CPF 12345678900.")


def test_vacancies_require_same_notice_and_publication_status() -> None:
    source = evidence(
        "Edital 006/2026: foram previstas 437 vagas.\n"
        "Edital 007/2026: foram previstas 25 vagas."
    )
    assert check(
        "O edital 006/2026 prevê 437 vagas.", [source],
    ) == FactStatus.VALUE_MATCH
    assert check(
        "O edital 007/2026 prevê 437 vagas.", [source],
    ) == FactStatus.VALUE_MISMATCH
    assert check(
        "Hoje há 437 vagas disponíveis.", [source],
        requires_current_state=True,
    ) == FactStatus.NO_ADMISSIBLE_SOURCE
    assert check("Existem 437 vagas livres.", [source]) == FactStatus.NO_ADMISSIBLE_SOURCE


def test_declared_entity_prevents_using_advanced_excel_to_validate_excel() -> None:
    standard = evidence("Excel tem 30 horas.", entity_id="curso:excel")
    advanced = evidence(
        "Excel Avançado tem 60 horas.", entity_id="curso:excel avancado",
    )
    assert check(
        "Excel tem 60 horas.", [standard, advanced],
        entity_id="curso:excel",
    ) == FactStatus.VALUE_MISMATCH
    assert check(
        "Excel Avançado tem 60 horas.", [standard, advanced],
        entity_id="curso:excel",
    ) == FactStatus.INSUFFICIENT_CONTEXT
    assert check(
        "Excel Avançado tem 60 horas.", [standard, advanced],
        entity_id="curso:excel avancado",
    ) == FactStatus.VALUE_MATCH
    assert check(
        "O curso dura 60 horas.", [standard, advanced],
    ) == FactStatus.AMBIGUOUS


def test_multi_offering_source_never_proves_unique_duration_or_price() -> None:
    source = official_source("cursos/informatica-basica-2026.md")
    assert check(
        "Informática Básica possui 80 horas.", [source],
        entity_id="curso:informatica basica",
    ) == FactStatus.AMBIGUOUS
    assert check(
        "Informática Básica custa R$ 620,00.", [source],
        entity_id="curso:informatica basica",
    ) == FactStatus.AMBIGUOUS
    assert check(
        "A idade mínima é 12 anos.", [source],
        entity_id="curso:informatica basica",
    ) == FactStatus.VALUE_MATCH


def test_real_official_sources_compare_values_but_not_entire_answer() -> None:
    excel = official_source("cursos/excel-2026.md")
    ouvido = official_source("atendimento/ouvidoria.md")
    contact = official_source("atendimento/canais-institucionais.md")
    psg = official_source("psg/vagas-e-editais.md")
    assert check(
        "Excel possui 30 horas.", [excel], entity_id="curso:excel",
    ) == FactStatus.VALUE_MATCH
    assert check(
        "A Ouvidoria responde em 15 dias úteis.", [ouvido],
    ) == FactStatus.VALUE_MATCH
    assert check(
        "O telefone central é (86) 3228-9500.", [contact],
    ) == FactStatus.VALUE_MATCH
    assert check(
        "O edital 006/2026 prevê 437 vagas.", [psg],
    ) == FactStatus.VALUE_MATCH
    assert check(
        "O edital 006/2026 prevê 25 vagas.", [psg],
    ) == FactStatus.VALUE_MISMATCH


def test_stale_or_untrusted_sources_never_confirm_numbers() -> None:
    text = "O curso tem 30 horas."
    assert check(
        "O curso tem 30 horas.", [evidence(text, authority="secondary")],
    ) == FactStatus.NO_ADMISSIBLE_SOURCE
    assert check(
        "O curso tem 30 horas.", [evidence(text, valid_until="2026-10-20")],
    ) == FactStatus.NO_ADMISSIBLE_SOURCE
    assert check(
        "O curso tem 30 horas.", [evidence(text, source_url="http://test.org")],
    ) == FactStatus.NO_ADMISSIBLE_SOURCE


def test_current_price_requires_editorial_confirmation_not_retrieved_at() -> None:
    old = evidence("Preço atual R$ 200,00", retrieved_at="2026-10-29")
    assert check(
        "O preço atual é R$ 200,00.", [old], requires_current_state=True,
    ) == FactStatus.NO_ADMISSIBLE_SOURCE
    recent = evidence(
        "Preço confirmado R$ 200,00",
        current_state_confirmed=True, verified_at="2026-10-29",
        valid_until="2026-10-29",
    )
    assert check(
        "O preço atual é R$ 200,00.", [recent],
        requires_current_state=True,
    ) == FactStatus.VALUE_MATCH


def test_unit_scope_requires_matching_unit_metadata() -> None:
    source = evidence("O curso custa R$ 100,00.", unit_id="teresina")
    assert check(
        "O curso custa R$ 100,00.", [source], unit_id="picos",
    ) == FactStatus.NO_ADMISSIBLE_SOURCE
    assert check(
        "O curso custa R$ 100,00.", [source], unit_id="teresina",
    ) == FactStatus.VALUE_MATCH
    assert check(
        "O curso custa R$ 100,00.", [evidence("O curso custa R$ 100,00.")],
        unit_id="teresina",
    ) == FactStatus.NO_ADMISSIBLE_SOURCE


def test_dates_need_valid_context_and_calendar() -> None:
    source = evidence("Data de inscrição: 29/10/2026.")
    assert check("A data de inscrição é 2026-10-29.", [source]) == FactStatus.VALUE_MATCH
    assert check("A data de inscrição é 2026-10-30.", [source]) == FactStatus.VALUE_MISMATCH
    assert not extract_explicit_facts("O número é 99/99/2026.")


def test_no_numbers_does_not_automatically_approve_nli() -> None:
    result = validate_claim_facts(
        "O Senac promove educação profissional.",
        [evidence("O Senac promove educação profissional.")],
        as_of=TODAY,
    )
    assert result.status == FactStatus.NOT_APPLICABLE
    assert result.as_dict()["full_claim_verified"] is False
    assert result.as_dict()["enforced"] is False



def test_explicit_entity_matching_respects_word_boundaries() -> None:
    from orelhao.services.knowledge.query_constraints import explicitly_named_entities
    entities = ("curso:excel", "curso:excel avancado")
    assert explicitly_named_entities(
        "Tenho interesse em Excel Avançado.", entities,
    ) == ("curso:excel avancado",)
    assert explicitly_named_entities(
        "Qual a duração do Excel?", entities,
    ) == ("curso:excel",)
    assert not explicitly_named_entities(
        "Exemplo de excelência no curso.", entities,
    )



def test_fact_check_includes_literal_source_offsets() -> None:
    source = evidence("Curso: 30 horas. Custo R$ 242,00.")
    result = validate_claim_facts("O curso dura 30 horas.", [source], as_of=TODAY)
    item = result.checks[0]
    assert item.source_start is not None and item.source_end is not None
    assert source.chunk.text[item.source_start:item.source_end] == item.supporting_literal
    assert result.as_dict()["checks"][0]["supporting_literal"] == "30 horas"
