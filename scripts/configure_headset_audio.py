"""Configure analog headset routing after PipeWire/WirePlumber startup.

This is server-specific provisioning, not a generic routing rule for all PCs.
"""
from __future__ import annotations

import logging
import subprocess
import time

import pulsectl  # type: ignore[import-untyped]

LOG = logging.getLogger(__name__)
SINK_PORT = "analog-output-headphones"
SOURCE_PORT = "analog-input-headset-mic"


def configure() -> None:
    error: Exception | None = None
    for _ in range(12):
        try:
            with pulsectl.Pulse("lumi-p3-routing") as pulse:
                sinks = [s for s in pulse.sink_list() if s.name.startswith("alsa_output.")]
                sources = [s for s in pulse.source_list() if s.name.startswith("alsa_input.")]
                if not sinks or not sources:
                    raise RuntimeError("Placa analógica ainda não disponível no PipeWire")
                sink, source = sinks[0], sources[0]
                if SINK_PORT not in [p.name for p in sink.port_list]:
                    raise RuntimeError("Saída física de fone P3 indisponível")
                if SOURCE_PORT not in [p.name for p in source.port_list]:
                    raise RuntimeError("Entrada física de microfone P3 indisponível")
                pulse.sink_port_set(sink.index, SINK_PORT)
                pulse.source_port_set(source.index, SOURCE_PORT)
                pulse.sink_mute(sink.index, False)
                pulse.source_mute(source.index, False)
            # Modest initial loudness. Increase only after supervised listening.
            for args in (
                ("wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "0.35"),
                ("wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"),
                ("wpctl", "set-volume", "@DEFAULT_AUDIO_SOURCE@", "0.20"),
            ):
                subprocess.run(args, check=True, timeout=5, capture_output=True)
            with pulsectl.Pulse("lumi-p3-routing-verification") as pulse:
                sink = next(s for s in pulse.sink_list() if s.name.startswith("alsa_output."))
                source = next(s for s in pulse.source_list() if s.name.startswith("alsa_input."))
                if (
                    sink.port_active is None or sink.port_active.name != SINK_PORT or sink.mute
                    or source.port_active is None or source.port_active.name != SOURCE_PORT
                    or source.mute
                ):
                    raise RuntimeError("Rotas do headset não confirmadas")
            LOG.info("Headset P3 configurado: fone e microfone selecionados")
            return
        except (OSError, RuntimeError, pulsectl.PulseError, subprocess.SubprocessError) as exc:
            error = exc
            time.sleep(1)
    raise RuntimeError(f"Não foi possível configurar a saída/entrada P3: {error}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    configure()
