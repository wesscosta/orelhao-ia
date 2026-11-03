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
                # A API Pulse conhece o sink correto, mesmo quando o wpctl não
                # possui @DEFAULT_AUDIO_SINK@ registrado no metadata PipeWire.
                pulse.volume_set_all_chans(sink, 0.35)
            # A placa HDA acopla o volume Pulse da fonte ao ganho ALSA: ajustar
            # o Pulse para 0.20 eleva Capture a 75% (+18dB) e satura a entrada.
            # A entrada física do Dell deve operar em ganho moderado e sem boost.
            subprocess.run(
                ("amixer", "-c", "0", "sset", "Capture", "40%", "cap"),
                check=True, timeout=5, capture_output=True,
            )
            with pulsectl.Pulse("lumi-p3-routing-verification") as pulse:
                sink = next(s for s in pulse.sink_list() if s.name.startswith("alsa_output."))
                source = next(s for s in pulse.source_list() if s.name.startswith("alsa_input."))
                if (
                    sink.port_active is None or sink.port_active.name != SINK_PORT or sink.mute
                    or source.port_active is None or source.port_active.name != SOURCE_PORT
                    or source.mute
                    or not 0.25 <= sink.volume.value_flat <= 0.45
                ):
                    raise RuntimeError("Rotas ou ganho de saída do headset não confirmados")
            LOG.info(
                "Headset P3 configurado: portas corretas, saída 35%, Capture 40%"
            )
            return
        except (OSError, RuntimeError, pulsectl.PulseError, subprocess.SubprocessError) as exc:
            error = exc
            time.sleep(1)
    raise RuntimeError(f"Não foi possível configurar a saída/entrada P3: {error}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    configure()
