"""Coleta leve, local e somente leitura da saúde do servidor Orelhão IA.

Fonte: /proc, /sys/class/hwmon e systemd do usuário. Não grava histórico,
não depende de psutil/sensors e nunca expõe argumentos ou caminhos de processos.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def cpu_percentage(before: tuple[int, int], after: tuple[int, int]) -> float | None:
    """Retorna uso de CPU entre duas leituras (total, idle+io_wait)."""
    total = after[0] - before[0]
    idle = after[1] - before[1]
    if total <= 0:
        return None
    return round(max(0.0, min(100.0, (total - max(0, idle)) * 100 / total)), 1)


def _cpu_ticks(proc: Path) -> tuple[int, int] | None:
    try:
        first = (proc / "stat").read_text(encoding="ascii").splitlines()[0].split()
        values = list(map(int, first[1:]))
        return sum(values), values[3] + values[4]
    except (OSError, ValueError, IndexError):
        return None


def _meminfo(proc: Path) -> dict[str, int]:
    try:
        lines = (proc / "meminfo").read_text(encoding="ascii").splitlines()
    except OSError:
        return {}
    found: dict[str, int] = {}
    for line in lines:
        name, _, value = line.partition(":")
        pieces = value.strip().split()
        if name in {"MemTotal", "MemAvailable", "MemFree", "SwapTotal", "SwapFree"} and pieces:
            try:
                found[name] = int(pieces[0]) * 1024
            except ValueError:
                continue
    return found


def _percentage(used: int, total: int) -> float | None:
    return round(100 * used / total, 1) if total > 0 else None


def _memory(proc: Path) -> dict[str, int | float | None]:
    info = _meminfo(proc)
    total = info.get("MemTotal", 0)
    available = info.get("MemAvailable", info.get("MemFree", 0))
    used = max(0, total - available)
    swap_total = info.get("SwapTotal", 0)
    swap_used = max(0, swap_total - info.get("SwapFree", 0))
    return {
        "total_bytes": total, "used_bytes": used, "available_bytes": available,
        "percent": _percentage(used, total), "swap_total_bytes": swap_total,
        "swap_used_bytes": swap_used, "swap_percent": _percentage(swap_used, swap_total),
    }


def _disk(path: Path) -> dict[str, int | float | None]:
    try:
        s = os.statvfs(path)
        total = s.f_blocks * s.f_frsize
        used = (s.f_blocks - s.f_bfree) * s.f_frsize
        available = s.f_bavail * s.f_frsize
        return {"total_bytes": total, "used_bytes": used,
                "available_bytes": available, "percent": _percentage(used, total)}
    except OSError:
        return {"total_bytes": 0, "used_bytes": 0, "available_bytes": 0, "percent": None}


def _temperatures(hwmon: Path) -> list[dict[str, str | float]]:
    """Usa os labels do kernel, sem duplicar zonas térmicas nem inventar sensores."""
    result: list[dict[str, str | float]] = []
    try:
        directories = sorted(hwmon.glob("hwmon*"))
    except OSError:
        return result
    for directory in directories:
        try:
            chip = (directory / "name").read_text(encoding="ascii").strip().lower()
        except OSError:
            continue
        if chip not in {"coretemp", "k10temp", "zenpower", "nvme"}:
            continue
        try:
            sensors = sorted(directory.glob("temp*_input"))
        except OSError:
            continue
        for sensor in sensors[:12]:
            try:
                celsius = int(sensor.read_text(encoding="ascii").strip()) / 1000
                if not -20 <= celsius <= 150:
                    continue
                label_file = sensor.with_name(sensor.name.replace("_input", "_label"))
                try:
                    label = label_file.read_text(encoding="utf-8").strip()
                except OSError:
                    label = "SSD" if chip == "nvme" else "Processador"
                group = "ssd" if chip == "nvme" else "cpu"
                result.append({"group": group, "label": label[:48], "celsius": round(celsius, 1)})
            except (OSError, ValueError):
                continue
    return result[:20]


_SERVICE_NAMES = {
    "orelhao-hook-voice.service": "Gancho ESP32 e voz",
    "orelhao-workbench-benchmark.service": "Knowledge Admin",
}


def _services() -> list[dict[str, str]]:
    """Consulta systemd sem privilégios, com prazo estrito de execução."""
    try:
        run = subprocess.run(
            ["systemctl", "--user", "is-active", *_SERVICE_NAMES],
            capture_output=True, text=True, timeout=1.5, check=False,
        )
        statuses = run.stdout.strip().splitlines()
    except (OSError, subprocess.TimeoutExpired):
        statuses = []
    return [
        {"name": label, "state": statuses[index] if index < len(statuses)
         and statuses[index] in {"active", "inactive", "failed", "activating", "deactivating"}
         else "unknown"}
        for index, label in enumerate(_SERVICE_NAMES.values())
    ]


def _processes(proc: Path) -> list[dict[str, str | int]]:
    """Somente nomes permitidos e RSS agregado; nunca PIDs, argumentos ou usuários."""
    chosen = {"llama-server": "LLM local", "orelhao": "Orelhão Admin"}
    totals: dict[str, tuple[int, int]] = {}
    try:
        entries = list(proc.iterdir())
    except OSError:
        return []
    for entry in entries:
        if not entry.name.isdecimal():
            continue
        try:
            name = (entry / "comm").read_text(encoding="utf-8").strip()
            label = chosen.get(name)
            if label is None:
                continue
            memory_kib = 0
            for line in (entry / "status").read_text(encoding="ascii").splitlines():
                if line.startswith("VmRSS:"):
                    memory_kib = int(line.split()[1])
                    break
            count, rss = totals.get(label, (0, 0))
            totals[label] = (count + 1, rss + memory_kib * 1024)
        except (OSError, ValueError, IndexError):
            continue
    return [
        {"name": name, "instances": count, "rss_bytes": rss}
        for name, (count, rss) in sorted(totals.items())
    ]


class SystemMetricsCollector:
    """Coleta agregados sob demanda; cache evita cargas repetidas de vários browsers."""

    def __init__(
        self, *, proc: Path = Path("/proc"), hwmon: Path = Path("/sys/class/hwmon"),
        disk: Path = Path("/"), cache_seconds: float = 4.0,
    ) -> None:
        self._proc = proc
        self._hwmon = hwmon
        self._disk = disk
        self._cache_seconds = cache_seconds
        self._lock = threading.Lock()
        self._last_time = 0.0
        self._last_cpu: tuple[int, int] | None = None
        self._snapshot: dict[str, Any] | None = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            if self._snapshot is not None and now - self._last_time < self._cache_seconds:
                return dict(self._snapshot)
            ticks = _cpu_ticks(self._proc)
            usage = cpu_percentage(self._last_cpu, ticks) if (
                ticks is not None and self._last_cpu is not None
            ) else None
            if ticks is not None:
                self._last_cpu = ticks
            try:
                load = [round(x, 2) for x in os.getloadavg()]
            except OSError:
                load = []
            try:
                uptime = max(0, int(float((self._proc / "uptime").read_text().split()[0])))
            except (OSError, ValueError, IndexError):
                uptime = None
            temperatures = _temperatures(self._hwmon)
            self._snapshot = {
                "sampled_at": datetime.now(UTC).isoformat(),
                "cpu": {"percent": usage, "logical_cores": os.cpu_count() or 1,
                        "load_average": load},
                "memory": _memory(self._proc),
                "disk": _disk(self._disk),
                "uptime_seconds": uptime,
                "temperatures": temperatures,
                "services": _services(),
                "processes": _processes(self._proc),
                "sampling_seconds": self._cache_seconds,
            }
            self._last_time = now
            return dict(self._snapshot)
