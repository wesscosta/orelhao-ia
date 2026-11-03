"""Validação conservadora de proveniência, unidade e informação temporal."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime

from .query_constraints import QueryConstraints, normalize


def parse_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def source_matches(metadata: Mapping[str, object], query: QueryConstraints) -> bool:
    """Apenas metadados com escopo explícito podem comprovar unidade/entidade."""
    unit = metadata.get("unit_id")
    if query.unit_id and unit and normalize(str(unit)) != query.unit_id:
        return False
    entity = metadata.get("entity_id")
    return not (
        query.entity_id and entity and normalize(str(entity)) != query.entity_id
    )


def current_state_is_verified(
    metadata: Mapping[str, object], query: QueryConstraints, *, as_of: date,
) -> bool:
    """Uma coleta recente não equivale à confirmação de vagas em tempo real.

    Exige declaração explícita do editor responsável e verificação no mesmo dia.
    """
    if not query.requires_current_state:
        return True
    if metadata.get("current_state_confirmed") is not True:
        return False
    if metadata.get("authority") != "primary":
        return False
    source_url = metadata.get("source_url")
    if not isinstance(source_url, str) or not source_url.startswith("https://"):
        return False
    verified_at = parse_date(metadata.get("verified_at"))
    valid_until = parse_date(metadata.get("valid_until"))
    return verified_at == as_of and valid_until is not None and valid_until >= as_of
