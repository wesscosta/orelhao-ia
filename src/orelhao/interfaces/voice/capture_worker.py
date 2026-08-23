from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from orelhao.config import AudioConfig
from orelhao.interfaces.voice.capture import ProcessIsolatedAudioCapture, SoundDeviceAudioCapture


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--wav", required=True)
    parser.add_argument("--diagnostics", required=True)
    args = parser.parse_args()

    config = AudioConfig.model_validate_json(Path(args.config).read_text(encoding="utf-8"))
    capture = SoundDeviceAudioCapture(config)

    def ready() -> None:
        print(ProcessIsolatedAudioCapture.READY_SENTINEL, flush=True)

    audio = capture.capture(on_ready=ready)
    if audio.data:
        Path(args.wav).write_bytes(audio.to_wav_bytes())
    if capture.last_diagnostics is not None:
        Path(args.diagnostics).write_text(
            json.dumps(asdict(capture.last_diagnostics), ensure_ascii=False),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
