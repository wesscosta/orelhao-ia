from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import numpy as np

from .index import load_chunks
from .models import SearchResult

SEMANTIC_INDEX_VERSION = 1
SEMANTIC_MODEL_ID = "intfloat/multilingual-e5-small"
SEMANTIC_MODEL_REVISION = "ccc66d3"
SEMANTIC_DIMENSIONS = 384
SEMANTIC_MODEL_FILENAME = "model_O4.onnx"
SEMANTIC_VECTORS_FILENAME = "semantic-vectors.npy"
SEMANTIC_MANIFEST_FILENAME = "semantic-manifest.json"


class SemanticVectorizer(Protocol):
    model_id: str
    model_revision: str
    dimensions: int

    def embed_queries(self, texts: Sequence[str]) -> np.ndarray: ...

    def embed_passages(self, texts: Sequence[str]) -> np.ndarray: ...


def default_semantic_model_dir(project_root: Path) -> Path:
    return project_root / "models" / "embeddings" / "multilingual-e5-small"


def provision_semantic_model(model_dir: Path) -> dict[str, str | int]:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:  # pragma: no cover - depende do extra opcional
        raise RuntimeError(
            "Dependências semânticas ausentes. Instale: pip install -e '.[semantic]'"
        ) from exc

    model_dir.mkdir(parents=True, exist_ok=True)
    files = {
        SEMANTIC_MODEL_FILENAME: "onnx/model_O4.onnx",
        "tokenizer.json": "tokenizer.json",
    }
    for local_name, remote_name in files.items():
        downloaded = hf_hub_download(
            repo_id=SEMANTIC_MODEL_ID,
            filename=remote_name,
            revision=SEMANTIC_MODEL_REVISION,
        )
        destination = model_dir / local_name
        shutil.copyfile(downloaded, destination)

    manifest: dict[str, str | int] = {
        "model_id": SEMANTIC_MODEL_ID,
        "revision": SEMANTIC_MODEL_REVISION,
        "dimensions": SEMANTIC_DIMENSIONS,
        "model_file": SEMANTIC_MODEL_FILENAME,
        "model_sha256": _sha256(model_dir / SEMANTIC_MODEL_FILENAME),
    }
    (model_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


class OnnxE5Vectorizer:
    model_id = SEMANTIC_MODEL_ID
    model_revision = SEMANTIC_MODEL_REVISION
    dimensions = SEMANTIC_DIMENSIONS

    def __init__(self, model_dir: Path, *, max_length: int = 512) -> None:
        try:
            import onnxruntime as ort  # type: ignore[import-untyped]
            from tokenizers import Tokenizer
        except ImportError as exc:  # pragma: no cover - depende do extra opcional
            raise RuntimeError(
                "Dependências semânticas ausentes. Instale: pip install -e '.[semantic]'"
            ) from exc

        model_path = model_dir / SEMANTIC_MODEL_FILENAME
        tokenizer_path = model_dir / "tokenizer.json"
        if not model_path.exists() or not tokenizer_path.exists():
            raise RuntimeError(
                "Modelo semântico local inexistente. Execute: "
                "orelhao knowledge semantic-provision"
            )

        self._tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self._tokenizer.enable_truncation(max_length=max_length)
        self._session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )
        self._input_names = {item.name for item in self._session.get_inputs()}

    def embed_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self._embed([f"query: {text}" for text in texts])

    def embed_passages(self, texts: Sequence[str]) -> np.ndarray:
        return self._embed([f"passage: {text}" for text in texts])

    def _embed(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimensions), dtype=np.float32)

        encodings = self._tokenizer.encode_batch(list(texts))
        width = max(len(item.ids) for item in encodings)
        input_ids = np.zeros((len(encodings), width), dtype=np.int64)
        attention_mask = np.zeros_like(input_ids)
        token_type_ids = np.zeros_like(input_ids)
        for row, encoding in enumerate(encodings):
            size = len(encoding.ids)
            input_ids[row, :size] = encoding.ids
            attention_mask[row, :size] = encoding.attention_mask
            token_type_ids[row, :size] = encoding.type_ids

        feeds: dict[str, np.ndarray] = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }
        if "token_type_ids" in self._input_names:
            feeds["token_type_ids"] = token_type_ids
        output = np.asarray(self._session.run(None, feeds)[0], dtype=np.float32)
        mask = attention_mask[:, :, None].astype(np.float32)
        pooled = (output * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1.0)
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        return np.asarray(pooled / np.maximum(norms, 1e-12), dtype=np.float32)


def build_semantic_index(
    index_dir: Path,
    vectorizer: SemanticVectorizer,
    *,
    batch_size: int = 8,
) -> dict[str, int | str]:
    if batch_size <= 0:
        raise ValueError("batch_size deve ser maior que zero")
    chunks = load_chunks(index_dir)
    batches = [
        vectorizer.embed_passages([chunk.text for chunk in chunks[start : start + batch_size]])
        for start in range(0, len(chunks), batch_size)
    ]
    vectors = (
        np.vstack(batches)
        if batches
        else np.empty((0, vectorizer.dimensions), dtype=np.float32)
    )
    if vectors.shape != (len(chunks), vectorizer.dimensions):
        raise RuntimeError("Vectorizer semântico retornou dimensões incompatíveis")

    vector_path = index_dir / SEMANTIC_VECTORS_FILENAME
    np.save(vector_path, vectors, allow_pickle=False)
    chunks_path = index_dir / "chunks.jsonl"
    manifest: dict[str, int | str] = {
        "version": SEMANTIC_INDEX_VERSION,
        "model_id": vectorizer.model_id,
        "model_revision": vectorizer.model_revision,
        "dimensions": vectorizer.dimensions,
        "chunks": len(chunks),
        "chunks_sha256": _sha256(chunks_path),
        "vectors_sha256": _sha256(vector_path),
    }
    (index_dir / SEMANTIC_MANIFEST_FILENAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


class SemanticRetriever:
    def __init__(
        self,
        index_dir: Path,
        vectorizer: SemanticVectorizer,
        *,
        min_score: float = 0.0,
    ) -> None:
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score deve estar entre 0 e 1")
        manifest_path = index_dir / SEMANTIC_MANIFEST_FILENAME
        vectors_path = index_dir / SEMANTIC_VECTORS_FILENAME
        if not manifest_path.exists() or not vectors_path.exists():
            raise RuntimeError(
                "Índice semântico inexistente. Execute: orelhao knowledge semantic-index"
            )

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("model_id") != vectorizer.model_id or manifest.get(
            "model_revision"
        ) != vectorizer.model_revision:
            raise RuntimeError("Índice semântico foi gerado com outro modelo ou revisão")
        self._chunks = load_chunks(index_dir)
        self._vectors = np.load(vectors_path, allow_pickle=False)
        if self._vectors.shape != (len(self._chunks), vectorizer.dimensions):
            raise RuntimeError("Índice semântico inconsistente")
        if manifest.get("chunks_sha256") != _sha256(index_dir / "chunks.jsonl"):
            raise RuntimeError("Índice semântico está desatualizado em relação aos chunks")
        self._vectorizer = vectorizer
        self.min_score = min_score

    def search(self, query: str, *, limit: int = 4) -> list[SearchResult]:
        if limit <= 0 or not query.strip() or not self._chunks:
            return []
        query_vector = self._vectorizer.embed_queries([query])[0]
        scores = self._vectors @ query_vector
        candidates = [
            (max(0.0, min(1.0, float(score))), position)
            for position, score in enumerate(scores)
            if float(score) >= self.min_score
        ]
        candidates.sort(key=lambda item: (-item[0], self._chunks[item[1]].source, item[1]))
        return [
            SearchResult(chunk=self._chunks[position], score=score)
            for score, position in candidates[:limit]
        ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
