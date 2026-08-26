from __future__ import annotations

import hashlib
import json
import math
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Protocol

import numpy as np

from .models import SearchResult
from .retriever import Retriever

EVIDENCE_MODEL_ID = "onnx-community/xlm-roberta-base-squad2-distilled-ONNX"
EVIDENCE_MODEL_REVISION = "484112fae76dde6ad01b640192d559cbc2d488e1"
EVIDENCE_MODEL_VARIANTS = {
    "int8": {
        "remote": "onnx/model_int8.onnx",
        "local": "model_int8.onnx",
    },
    "fp32": {
        "remote": "onnx/model.onnx",
        "local": "model_fp32.onnx",
    },
}
EVIDENCE_MODEL_FILENAME = EVIDENCE_MODEL_VARIANTS["int8"]["local"]


class EvidenceVerifier(Protocol):
    def support_score(self, query: str, passage: str) -> float: ...


def evidence_model_filename(variant: str) -> str:
    try:
        return EVIDENCE_MODEL_VARIANTS[variant]["local"]
    except KeyError as exc:
        choices = ", ".join(EVIDENCE_MODEL_VARIANTS)
        raise ValueError(f"variant deve ser uma de: {choices}") from exc


def provision_evidence_model(
    model_dir: Path,
    *,
    variant: str = "int8",
) -> dict[str, str | int]:
    model_filename = evidence_model_filename(variant)
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:  # pragma: no cover - depende do extra opcional
        raise RuntimeError(
            "Dependências de evidência ausentes. Instale: pip install -e '.[evidence]'"
        ) from exc

    model_dir.mkdir(parents=True, exist_ok=True)
    files = {
        model_filename: EVIDENCE_MODEL_VARIANTS[variant]["remote"],
        "tokenizer.json": "tokenizer.json",
    }
    for local_name, remote_name in files.items():
        downloaded = hf_hub_download(
            repo_id=EVIDENCE_MODEL_ID,
            filename=remote_name,
            revision=EVIDENCE_MODEL_REVISION,
        )
        shutil.copyfile(downloaded, model_dir / local_name)

    manifest: dict[str, str | int] = {
        "model_id": EVIDENCE_MODEL_ID,
        "revision": EVIDENCE_MODEL_REVISION,
        "variant": variant,
        "model_file": model_filename,
        "model_size_bytes": (model_dir / model_filename).stat().st_size,
        "model_sha256": _sha256(model_dir / model_filename),
    }
    (model_dir / f"manifest-{variant}.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if variant == "int8":
        (model_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return manifest


class OnnxExtractiveQaEvidenceVerifier:
    """Estima se um chunk contém uma resposta extraível para a pergunta."""

    def __init__(
        self,
        model_dir: Path,
        *,
        variant: str = "int8",
        max_length: int = 384,
        max_answer_tokens: int = 32,
    ) -> None:
        if max_length <= 0 or max_answer_tokens <= 0:
            raise ValueError("limites do verificador devem ser maiores que zero")
        try:
            import onnxruntime as ort  # type: ignore[import-untyped]
            from tokenizers import Tokenizer
        except ImportError as exc:  # pragma: no cover - depende do extra opcional
            raise RuntimeError(
                "Dependências de evidência ausentes. Instale: pip install -e '.[evidence]'"
            ) from exc

        model_path = model_dir / evidence_model_filename(variant)
        tokenizer_path = model_dir / "tokenizer.json"
        if not model_path.exists() or not tokenizer_path.exists():
            raise RuntimeError(
                "Modelo de evidência local inexistente. Execute: "
                f"orelhao knowledge evidence-provision --variant {variant}"
            )

        self._tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self._tokenizer.enable_truncation(max_length=max_length, strategy="only_second")
        self._session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )
        self._input_names = {item.name for item in self._session.get_inputs()}
        self._output_names = [item.name for item in self._session.get_outputs()]
        self._max_answer_tokens = max_answer_tokens
        self.variant = variant
        self.model_path = model_path

    def support_score(self, query: str, passage: str) -> float:
        if not query.strip() or not passage.strip():
            return 0.0
        encoding = self._tokenizer.encode(query, passage)
        input_ids = np.asarray([encoding.ids], dtype=np.int64)
        attention_mask = np.asarray([encoding.attention_mask], dtype=np.int64)
        token_type_ids = np.asarray([encoding.type_ids], dtype=np.int64)
        feeds: dict[str, np.ndarray] = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }
        if "token_type_ids" in self._input_names:
            feeds["token_type_ids"] = token_type_ids

        raw_outputs = self._session.run(None, feeds)
        outputs = {
            name: np.asarray(value, dtype=np.float32)[0]
            for name, value in zip(self._output_names, raw_outputs, strict=True)
        }
        try:
            start_logits = outputs["start_logits"]
            end_logits = outputs["end_logits"]
        except KeyError as exc:
            raise RuntimeError("Modelo de evidência não expõe logits de QA") from exc

        null_score = float(start_logits[0] + end_logits[0])
        context_positions = [
            index for index, sequence_id in enumerate(encoding.sequence_ids) if sequence_id == 1
        ]
        best_span_score = -math.inf
        for start in context_positions:
            maximum_end = min(start + self._max_answer_tokens, len(end_logits))
            for end in range(start, maximum_end):
                if encoding.sequence_ids[end] != 1:
                    break
                best_span_score = max(
                    best_span_score,
                    float(start_logits[start] + end_logits[end]),
                )
        if not math.isfinite(best_span_score):
            return 0.0
        return _sigmoid(best_span_score - null_score)


class EvidenceFilteredRetriever:
    def __init__(
        self,
        retriever: Retriever,
        verifier: EvidenceVerifier,
        *,
        min_support: float = 0.5,
    ) -> None:
        if not 0.0 <= min_support <= 1.0:
            raise ValueError("min_support deve estar entre 0 e 1")
        self._retriever = retriever
        self._verifier = verifier
        self.min_support = min_support

    def search(self, query: str, *, limit: int = 4) -> list[SearchResult]:
        if limit <= 0 or not query.strip():
            return []
        candidates = self._retriever.search(query, limit=limit)
        supported: list[SearchResult] = []
        for result in candidates:
            support = self._verifier.support_score(query, result.chunk.text)
            if support < self.min_support:
                continue
            metadata = dict(result.chunk.metadata)
            metadata["evidence_support"] = f"{support:.6f}"
            supported.append(
                SearchResult(
                    chunk=replace(result.chunk, metadata=metadata),
                    score=result.score,
                )
            )
        return supported


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        return 1.0 / (1.0 + math.exp(-value))
    exponential = math.exp(value)
    return exponential / (1.0 + exponential)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
