from __future__ import annotations

import hashlib
from pathlib import Path

from .models import Document

SUPPORTED_SUFFIXES = {".md", ".txt"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_documents(directory: Path) -> list[Document]:
    if not directory.exists():
        return []

    documents: list[Document] = []
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        if path.name.startswith(".") or path.suffix.casefold() not in SUPPORTED_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        relative = path.relative_to(directory).as_posix()
        documents.append(
            Document(
                id=relative,
                title=path.stem,
                source=relative,
                text=text,
                metadata={"sha256": file_sha256(path), "format": path.suffix.casefold().lstrip(".")},
            )
        )
    return documents
