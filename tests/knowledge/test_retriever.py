from orelhao.services.knowledge import Document, KnowledgeService


def _knowledge() -> KnowledgeService:
    service = KnowledgeService()
    service.ingest(
        [
            Document(
                id="offline",
                source="docs/offline.md",
                text="O terminal funciona offline com modelos e base provisionados localmente.",
            ),
            Document(
                id="touch",
                source="docs/touch.md",
                text="A interface touch é opcional e não é requisito para o fluxo de voz.",
            ),
        ],
        chunk_size=200,
        overlap=20,
    )
    return service


def test_retrieval_returns_relevant_source_first() -> None:
    context = _knowledge().retrieve("o terminal funciona offline?", limit=2)
    assert context.has_evidence
    assert context.results[0].chunk.source == "docs/offline.md"
    assert "offline" in context.text.casefold()


def test_retrieval_without_overlap_has_no_evidence() -> None:
    context = _knowledge().retrieve("astronomia quasar", limit=3)
    assert not context.has_evidence
    assert context.text == ""


def test_domain_is_defined_by_documents_not_core() -> None:
    service = KnowledgeService()
    service.ingest(
        [Document(id="museum", source="museum/faq.md", text="A exposição abre às nove horas.")],
        chunk_size=120,
        overlap=10,
    )
    context = service.retrieve("que horas a exposição abre?")
    assert context.has_evidence
    assert "nove horas" in context.text
