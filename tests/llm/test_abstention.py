from __future__ import annotations

import pytest

from orelhao.services.llm.abstention import INSUFFICIENT_CONTEXT, normalize_abstention


@pytest.mark.parametrize("answer", [
    "O preço do curso de teste não é especificado nas evidências fornecidas.",
    "Essa informação não consta no contexto fornecido.",
    "O dado não foi informado nos documentos apresentados.",
    "INSUFFICIENT_CONTEXT",
    "INSUFFICIENT_CONTEXT.",
    "INSUFFICIENT_CONTEXT\n\nINSUFFICIENT_CONTEXT",
    "INSUFFICIENT_CONTEXT! ",
])
def test_normalize_pure_refusal(answer: str) -> None:
    assert normalize_abstention(answer) == INSUFFICIENT_CONTEXT


@pytest.mark.parametrize("answer", [
    "O curso é gratuito.",
    "A evidência diz que o preço não é especificado, mas o curso custa R$ 200.",
    "O dado não consta no contexto. Entretanto o valor é R$ 90.",
    "Os dados não são mencionados no contrato, mas o prazo é de 40 dias.",
])
def test_do_not_normalize_mixed_or_real_answers(answer: str) -> None:
    assert normalize_abstention(answer) == answer
