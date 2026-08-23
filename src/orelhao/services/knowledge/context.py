from __future__ import annotations

from .models import KnowledgeContext, SearchResult


class ContextBuilder:
    def __init__(self, *, max_chars: int = 4_000) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars deve ser positivo")
        self.max_chars = max_chars

    def build(self, query: str, results: list[SearchResult]) -> KnowledgeContext:
        selected: list[SearchResult] = []
        sections: list[str] = []
        used = 0

        for index, result in enumerate(results, start=1):
            header = f"[Fonte {index}: {result.chunk.source}]\n"
            section = header + result.chunk.text.strip()
            separator = "\n\n" if sections else ""
            remaining = self.max_chars - used - len(separator)
            if remaining <= len(header):
                break
            if len(section) > remaining:
                body_limit = remaining - len(header)
                section = header + result.chunk.text.strip()[:body_limit].rstrip()
            sections.append(section)
            selected.append(result)
            used += len(separator) + len(section)
            if used >= self.max_chars:
                break

        return KnowledgeContext(query=query, text="\n\n".join(sections), results=tuple(selected))
