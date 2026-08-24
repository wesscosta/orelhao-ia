from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from .models import Document

SUPPORTED_SUFFIXES = {".md", ".txt"}
CONTROL_FILENAMES = {"00-readme.md"}
EXCLUDED_CATEGORIES = {"evaluation"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_markdown_frontmatter(text: str) -> tuple[str, dict[str, Any]]:
    """Extrai YAML frontmatter de um documento Markdown.

    O frontmatter é convertido em metadata e removido do conteúdo
    que será posteriormente fragmentado e vetorizado.
    """
    if not text.startswith("---"):
        return text.strip(), {}

    lines = text.splitlines()

    if not lines or lines[0].strip() != "---":
        return text.strip(), {}

    closing_index: int | None = None

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break

    if closing_index is None:
        return text.strip(), {}

    raw_frontmatter = "\n".join(lines[1:closing_index])

    try:
        parsed = yaml.safe_load(raw_frontmatter) or {}
    except yaml.YAMLError:
        # Frontmatter inválido não deve destruir a ingestão.
        # Nesse caso, preservamos o documento integralmente.
        return text.strip(), {}

    if not isinstance(parsed, dict):
        return text.strip(), {}

    metadata = {str(key): value for key, value in parsed.items()}
    content = "\n".join(lines[closing_index + 1 :]).strip()

    return content, metadata


def _should_index(relative: str, metadata: dict[str, Any]) -> bool:
    filename = Path(relative).name.casefold()

    if filename in CONTROL_FILENAMES:
        return False

    category = str(metadata.get("category", "")).strip().casefold()

    return category not in EXCLUDED_CATEGORIES


def load_documents(directory: Path) -> list[Document]:
    if not directory.exists():
        return []

    documents: list[Document] = []

    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        if path.name.startswith(".") or path.suffix.casefold() not in SUPPORTED_SUFFIXES:
            continue

        raw_text = path.read_text(encoding="utf-8").strip()

        if not raw_text:
            continue

        relative = path.relative_to(directory).as_posix()

        frontmatter: dict[str, Any] = {}
        text = raw_text

        if path.suffix.casefold() == ".md":
            text, frontmatter = _parse_markdown_frontmatter(raw_text)

        if not _should_index(relative, frontmatter):
            continue

        if not text:
            continue

        metadata: dict[str, Any] = {
            "sha256": file_sha256(path),
            "format": path.suffix.casefold().lstrip("."),
            **frontmatter,
        }

        title = str(frontmatter.get("title") or path.stem)

        documents.append(
            Document(
                id=relative,
                title=title,
                source=relative,
                text=text,
                metadata=metadata,
            )
        )

    return documents
