from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

MAX_SOURCE_BYTES = 2 * 1024 * 1024
ALLOWED_SUFFIXES = {".md", ".txt"}


@dataclass(frozen=True, slots=True)
class SourceFile:
    name: str
    relative_path: str
    size_bytes: int
    sha256: str


def _safe_component(value: str) -> str:
    value = value.strip().replace("\\", "-").replace("/", "-")
    value = re.sub(r"[^\w. -]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-.")
    if not value:
        raise ValueError("Nome de arquivo inválido")
    return value


def normalize_source_name(filename: str) -> str:
    name = _safe_component(Path(filename).name)
    suffix = Path(name).suffix.casefold()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("Formato não suportado. Use .md ou .txt")
    if suffix == ".txt":
        name = f"{Path(name).stem}.md"
    return name


def list_sources(directory: Path) -> list[SourceFile]:
    if not directory.exists():
        return []
    items: list[SourceFile] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.casefold() not in ALLOWED_SUFFIXES:
            continue
        items.append(
            SourceFile(
                name=path.name,
                relative_path=path.relative_to(directory).as_posix(),
                size_bytes=path.stat().st_size,
                sha256=_file_sha256(path),
            )
        )
    return items



def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def create_markdown_source(
    directory: Path,
    *,
    filename: str,
    title: str,
    tags: str = "",
) -> Path:
    raw_name = filename.strip() or title.strip() or "documento"
    if not raw_name.casefold().endswith(".md"):
        raw_name += ".md"
    target_name = normalize_source_name(raw_name)
    path = resolve_source(directory, target_name)
    if path.exists():
        raise ValueError("Já existe uma fonte com esse nome")
    resolved_title = title.strip() or Path(target_name).stem.replace("-", " ")
    content = f"{_frontmatter(resolved_title, tags)}# {resolved_title}\n\n"
    return atomic_write_source(directory, target_name, content)


def delete_source(directory: Path, relative_path: str) -> None:
    path = resolve_source(directory, relative_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(relative_path)
    if path.suffix.casefold() not in ALLOWED_SUFFIXES:
        raise ValueError("Formato de fonte inválido")
    path.unlink()

def resolve_source(directory: Path, relative_path: str) -> Path:
    root = directory.resolve()
    candidate = (directory / relative_path).resolve()
    if root not in candidate.parents and candidate != root:
        raise ValueError("Caminho inválido")
    return candidate


def read_source(directory: Path, relative_path: str) -> str:
    path = resolve_source(directory, relative_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(relative_path)
    return path.read_text(encoding="utf-8")


def _frontmatter(title: str | None, tags: str | None) -> str:
    title = (title or "").strip()
    tag_items = [item.strip() for item in (tags or "").split(",") if item.strip()]
    if not title and not tag_items:
        return ""
    lines = ["---"]
    if title:
        escaped = title.replace('"', '\\"')
        lines.append(f'title: "{escaped}"')
    if tag_items:
        lines.append("tags:")
        lines.extend(f"  - {item}" for item in tag_items)
    lines.extend(["---", ""])
    return "\n".join(lines)


def normalize_uploaded_text(
    *,
    original_name: str,
    raw_text: str,
    title: str | None = None,
    tags: str | None = None,
) -> tuple[str, str]:
    target_name = normalize_source_name(original_name)
    body = raw_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not body:
        raise ValueError("Documento vazio")

    suffix = Path(original_name).suffix.casefold()
    if suffix == ".txt":
        resolved_title = (title or Path(original_name).stem).strip()
        body = f"# {resolved_title}\n\n{body}"

    # Não duplica frontmatter existente em Markdown.
    prefix = "" if body.startswith("---\n") else _frontmatter(title, tags)
    return target_name, f"{prefix}{body}\n"


def atomic_write_source(directory: Path, relative_path: str, content: str) -> Path:
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_SOURCE_BYTES:
        raise ValueError("Documento excede o limite de 2 MiB")

    path = resolve_source(directory, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".orelhao-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return path
