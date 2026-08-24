from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import numpy as np

from .index import VECTOR_DIMENSIONS, load_chunks, load_vectors
from .models import Chunk, SearchResult
from .vectorizer import hashing_vector

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = {
    "a", "ao", "aos", "as",
    "como",
    "da", "das", "de", "do", "dos",
    "e", "em", "eu",
    "faz", "faco",
    "fica", "foi",
    "me",
    "no", "nos", "na", "nas",
    "o", "os",
    "se",
    "para", "por",
    "qual", "que",
    "uma", "um",
}

# Sinônimos deliberadamente genéricos.
# Não devem existir aqui regras específicas de uma organização/corpus.
_SYNONYMS = {
    "endereco": {
        "endereco",
        "localizacao",
        "local",
        "fica",
    },
    "localizacao": {
        "localizacao",
        "endereco",
        "local",
        "fica",
    },
    "inscrever": {
        "inscrever",
        "inscricao",
        "matricula",
        "matricular",
    },
    "inscricao": {
        "inscricao",
        "inscrever",
        "matricula",
        "matricular",
    },
    "matricula": {
        "matricula",
        "matricular",
        "inscricao",
        "inscrever",
    },
    "matricular": {
        "matricular",
        "matricula",
        "inscricao",
        "inscrever",
    },
    "unidade": {
        "unidade",
        "unidades",
    },
}


def _normalize(text: str) -> str:
    value = unicodedata.normalize(
        "NFKD",
        text.casefold(),
    )

    return "".join(
        ch
        for ch in value
        if not unicodedata.combining(ch)
    )


def _tokens(text: str) -> set[str]:
    return set(
        _TOKEN_RE.findall(
            _normalize(text)
        )
    )


def _query_terms(query: str) -> set[str]:
    return {
        token
        for token in _tokens(query)
        if (
            token not in _STOPWORDS
            and len(token) >= 2
        )
    }


def _expanded_terms(
    terms: set[str],
) -> set[str]:
    expanded = set(terms)

    for term in terms:
        expanded.update(
            _SYNONYMS.get(term, ())
        )

    return expanded


def _field_tokens(
    chunk: Chunk,
) -> tuple[
    set[str],
    set[str],
    set[str],
    set[str],
]:
    """Separa evidência textual de sinais estruturais."""

    body_tokens = _tokens(chunk.text)

    title_tokens = _tokens(
        str(
            chunk.metadata.get(
                "title",
                "",
            )
        )
    )

    source_tokens = _tokens(
        chunk.source
        .replace("/", " ")
        .replace("-", " ")
        .replace("_", " ")
    )

    category_tokens = _tokens(
        str(
            chunk.metadata.get(
                "category",
                "",
            )
        )
    )

    return (
        body_tokens,
        title_tokens,
        source_tokens,
        category_tokens,
    )


def _term_matches(
    term: str,
    tokens: set[str],
) -> bool:
    alternatives = _SYNONYMS.get(
        term,
        {term},
    )

    return bool(
        alternatives & tokens
    )


def _lexical_score(
    query: str,
    chunk: Chunk,
) -> tuple[float, float]:
    """Calcula relevância lexical e cobertura do conteúdo.

    A cobertura é baseada exclusivamente no corpo do chunk.
    Título, source e category funcionam apenas como sinais
    auxiliares de ranking.
    """

    terms = _query_terms(query)

    if not terms:
        return 0.0, 0.0

    (
        body_tokens,
        title_tokens,
        source_tokens,
        category_tokens,
    ) = _field_tokens(chunk)

    # Evidência principal: conteúdo real do chunk.
    matched_body_terms = sum(
        1
        for term in terms
        if _term_matches(
            term,
            body_tokens,
        )
    )

    coverage = (
        matched_body_terms
        / len(terms)
    )

    lexical = coverage

    expanded = _expanded_terms(terms)

    # Metadados ajudam no ranking, mas não substituem
    # evidência existente no conteúdo.
    title_overlap = len(
        expanded & title_tokens
    )

    source_overlap = len(
        expanded & source_tokens
    )

    category_overlap = len(
        expanded & category_tokens
    )

    if title_overlap:
        lexical += min(
            0.10,
            title_overlap * 0.04,
        )

    if source_overlap:
        lexical += min(
            0.06,
            source_overlap * 0.03,
        )

    if category_overlap:
        lexical += min(
            0.08,
            category_overlap * 0.04,
        )

    # Perguntas operacionais recebem um pequeno sinal
    # adicional quando a ação aparece explicitamente
    # na estrutura do documento.
    action_terms = {
        "inscrever",
        "inscricao",
        "matricula",
        "matricular",
        "consultar",
        "solicitar",
        "acompanhar",
        "cancelar",
        "renovar",
        "emitir",
        "acessar",
    }

    query_actions = (
        expanded
        & action_terms
    )

    matched_action = False

    for action in query_actions:
        alternatives = _SYNONYMS.get(
            action,
            {action},
        )

        # Intenção operacional é um sinal de compatibilidade,
        # não uma substituição da evidência textual. O corpo
        # continua determinando a cobertura; título/source
        # apenas ajudam a desempatar documentos que realmente
        # tratam da ação solicitada.
        if alternatives & body_tokens:
            matched_action = True
            lexical += 0.08

        if alternatives & title_tokens:
            matched_action = True
            lexical += 0.06

        elif alternatives & source_tokens:
            matched_action = True
            lexical += 0.04

    # Em uma pergunta operacional (inscrever, solicitar,
    # consultar...), um documento puramente descritivo pode
    # compartilhar o assunto e ainda assim não responder à
    # intenção. Reduzimos esse falso positivo sem promover
    # título acima do conteúdo.
    if query_actions and not matched_action:
        lexical *= 0.55

    return (
        min(1.0, lexical),
        coverage,
    )


def _hybrid_score(
    *,
    vector_score: float,
    lexical_score: float,
    coverage: float,
) -> float:
    """Combina recuperação vetorial e evidência lexical."""

    vector_score = max(
        0.0,
        min(
            1.0,
            vector_score,
        ),
    )

    # Hash collision isolada não constitui evidência.
    if coverage <= 0.0:
        return 0.0

    # Cobertura muito pequena continua sendo insuficiente.
    # Entre 25% e 34%, aceitamos o candidato somente quando
    # há forte alinhamento lexical/operacional. Isso evita que
    # uma pergunta como "como me inscrevo no programa X" perca
    # o documento procedural apenas porque ele não repete o
    # nome completo do programa em cada chunk.
    if coverage < 0.25:
        return 0.0

    if (
        coverage < 0.34
        and lexical_score < 0.50
    ):
        return 0.0

    score = (
        lexical_score * 0.65
        + vector_score * 0.35
    )

    return max(
        0.0,
        min(
            1.0,
            score,
        ),
    )


class PersistentVectorRetriever:
    """Retriever híbrido local e persistente.

    Combina:

    - hashing vetorial;
    - cobertura lexical do conteúdo;
    - título;
    - categoria;
    - caminho da fonte;
    - pequenos sinais de intenção operacional.

    O conteúdo permanece a evidência principal.
    Metadados atuam apenas como sinais auxiliares.

    A implementação é totalmente local e offline.
    """

    def __init__(
        self,
        index_dir: Path,
        *,
        min_score: float = 0.40,
    ) -> None:
        if not 0.0 <= min_score <= 1.0:
            raise ValueError(
                "min_score deve estar "
                "entre 0 e 1"
            )

        self.index_dir = index_dir
        self.min_score = min_score

        self._chunks = load_chunks(
            index_dir
        )

        self._vectors = load_vectors(
            index_dir
        )

        if (
            len(self._chunks)
            != len(self._vectors)
        ):
            raise RuntimeError(
                "Índice inconsistente: "
                "quantidade de chunks "
                "e vetores diverge"
            )

    def search(
        self,
        query: str,
        *,
        limit: int = 4,
    ) -> list[SearchResult]:
        if (
            limit <= 0
            or not query.strip()
            or not self._chunks
        ):
            return []

        query_vector = hashing_vector(
            query,
            dimensions=VECTOR_DIMENSIONS,
        )

        if not np.any(
            query_vector
        ):
            return []

        vector_scores = (
            self._vectors
            @ query_vector
        )

        candidates: list[
            tuple[float, int]
        ] = []

        for index, chunk in enumerate(
            self._chunks
        ):
            vector_score = float(
                vector_scores[index]
            )

            (
                lexical_score,
                coverage,
            ) = _lexical_score(
                query,
                chunk,
            )

            score = _hybrid_score(
                vector_score=vector_score,
                lexical_score=lexical_score,
                coverage=coverage,
            )

            if (
                score
                >= self.min_score
            ):
                candidates.append(
                    (
                        score,
                        index,
                    )
                )

        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return [
            SearchResult(
                chunk=self._chunks[index],
                score=score,
            )
            for score, index
            in candidates[:limit]
        ]
