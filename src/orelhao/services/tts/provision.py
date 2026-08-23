from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from orelhao.config import TTSConfig
from orelhao.runtime_paths import resolve_project_path


@dataclass(frozen=True, slots=True)
class ProvisionedVoice:
    model: Path
    config: Path
    model_card: Path


def provision_piper_voice(cfg: TTSConfig) -> ProvisionedVoice:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError(
            "huggingface-hub não instalado. Execute: pip install -e '.[tts]'"
        ) from exc

    targets = {
        cfg.voice_model_file: resolve_project_path(cfg.model),
        cfg.voice_config_file: resolve_project_path(cfg.config or (cfg.model + ".json")),
        cfg.voice_model_card_file: resolve_project_path(cfg.model).parent / "MODEL_CARD",
    }
    downloaded: dict[str, Path] = {}
    for remote, target in targets.items():
        source = Path(hf_hub_download(repo_id=cfg.voice_repo, filename=remote))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        downloaded[remote] = target

    return ProvisionedVoice(
        model=downloaded[cfg.voice_model_file],
        config=downloaded[cfg.voice_config_file],
        model_card=downloaded[cfg.voice_model_card_file],
    )
