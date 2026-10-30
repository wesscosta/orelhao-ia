"""Instala exclusivamente a voz Piper Faber, sem alterar Cadu.

Uso: python scripts/provision_piper_faber.py
Requer huggingface-hub (extra [tts]); rede apenas durante provisionamento.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from orelhao.runtime_paths import resolve_project_path

REPO_ID = "rhasspy/piper-voices"
PREFIX = "pt/pt_BR/faber/medium"
TARGET = "pt_BR-faber-medium"


def main() -> None:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise SystemExit(
            "huggingface-hub ausente: instale as dependências TTS do projeto."
        ) from exc

    folder = resolve_project_path("models/tts")
    folder.mkdir(parents=True, exist_ok=True)
    for filename, destination in (
        (f"{TARGET}.onnx", f"{TARGET}.onnx"),
        (f"{TARGET}.onnx.json", f"{TARGET}.onnx.json"),
        ("MODEL_CARD", f"{TARGET}.MODEL_CARD"),
    ):
        remote = f"{PREFIX}/{filename}"
        source = Path(hf_hub_download(repo_id=REPO_ID, filename=remote))
        target = folder / destination
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        print(f"Pronto: {target} ({target.stat().st_size} bytes)")

    print("Voz disponível na bancada: faber (sem modificar a configuração Cadu).")


if __name__ == "__main__":
    main()
