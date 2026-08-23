from orelhao.services.knowledge.context import ContextBuilder
from orelhao.services.knowledge.models import Chunk, SearchResult


def test_context_builder_respects_budget_and_keeps_source() -> None:
    result = SearchResult(
        chunk=Chunk(
            id="a:0",
            document_id="a",
            text="x" * 500,
            source="base/a.md",
            position=0,
        ),
        score=1.0,
    )
    context = ContextBuilder(max_chars=120).build("q", [result])
    assert len(context.text) <= 120
    assert "base/a.md" in context.text
    assert context.has_evidence
