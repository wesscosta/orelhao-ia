"""Telemetria da máquina: dados locais, não invasivos e leitura pelo Admin."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from orelhao.admin import system_metrics
from orelhao.admin.app import create_admin_app
from orelhao.admin.system_metrics import (
    SystemMetricsCollector,
    _memory,
    _processes,
    _temperatures,
    cpu_percentage,
)


def test_cpu_percent_usa_delta_e_trata_primeira_leitura() -> None:
    assert cpu_percentage((100, 40), (200, 60)) == 80.0
    assert cpu_percentage((100, 40), (100, 40)) is None
    assert cpu_percentage((100, 40), (105, 95)) == 0.0


def test_memoria_retirada_de_meminfo_sem_vazar_outros_dados(tmp_path: Path) -> None:
    (tmp_path / "meminfo").write_text(
        "MemTotal: 8000000 kB\nMemAvailable: 3000000 kB\n"
        "SwapTotal: 2000000 kB\nSwapFree: 1500000 kB\n",
        encoding="ascii",
    )
    data = _memory(tmp_path)
    assert data["percent"] == 62.5
    assert data["swap_percent"] == 25.0
    assert data["available_bytes"] == 3000000 * 1024


def test_temperatura_do_kernel_preserva_rotulos_sem_erros(tmp_path: Path) -> None:
    cpu = tmp_path / "hwmon2"
    ssd = tmp_path / "hwmon1"
    fake = tmp_path / "hwmon3"
    for p in (cpu, ssd, fake):
        p.mkdir()
    (cpu / "name").write_text("coretemp\n")
    (cpu / "temp1_input").write_text("41900\n")
    (cpu / "temp1_label").write_text("Package id 0\n")
    (ssd / "name").write_text("nvme\n")
    (ssd / "temp1_input").write_text("40750\n")
    (fake / "name").write_text("untrustedchip\n")
    (fake / "temp1_input").write_text("99999\n")

    readings = _temperatures(tmp_path)
    assert readings == [
        {"group": "ssd", "label": "SSD", "celsius": 40.8},
        {"group": "cpu", "label": "Package id 0", "celsius": 41.9},
    ]


def test_processos_omitem_pids_argumentos_usuarios_e_outros_nomes(tmp_path: Path) -> None:
    for pid, name, rss in [
        ("123", "llama-server", "VmRSS: 245760 kB\n"),
        ("124", "python", "VmRSS: 600000 kB\n"),
        ("125", "orelhao", "VmRSS: 25000 kB\n"),
    ]:
        proc = tmp_path / pid
        proc.mkdir()
        (proc / "comm").write_text(name)
        (proc / "status").write_text(rss)
        (proc / "cmdline").write_text("SECRET-DO-NOSSO-SERVIDOR")
    items = _processes(tmp_path)
    assert len(items) == 2
    assert all(set(item) == {"name", "instances", "rss_bytes"} for item in items)
    assert "SECRET" not in str(items)
    assert "123" not in str(items)


def test_snapshot_com_cache_impede_leituras_repetidas(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "stat").write_text("cpu  100 0 20 200 0 0 0\n")
    (tmp_path / "uptime").write_text("3600.5 2000.0\n")
    (tmp_path / "meminfo").write_text(
        "MemTotal: 1000 kB\nMemAvailable: 500 kB\n"
        "SwapTotal: 0 kB\nSwapFree: 0 kB\n"
    )
    (tmp_path / "hwmon0").mkdir()
    (tmp_path / "hwmon0" / "name").write_text("unknown")
    calls: list[str] = []

    def fake_run(*args, **kwargs):
        calls.append("systemctl")
        return SimpleNamespace(returncode=0, stdout="active\nactive\n")

    monkeypatch.setattr(system_metrics.subprocess, "run", fake_run)
    collector = SystemMetricsCollector(
        proc=tmp_path, hwmon=tmp_path, disk=tmp_path, cache_seconds=60,
    )
    first = collector.snapshot()
    assert first["cpu"]["percent"] is None
    assert first["memory"]["percent"] == 50.0
    assert first["uptime_seconds"] == 3600
    assert first["services"][0]["state"] == "active"
    assert collector.snapshot() == first
    assert calls == ["systemctl"]


def test_metricas_sem_sensores_sao_indisponiveis_sem_valores_inventados(tmp_path: Path) -> None:
    assert _temperatures(tmp_path) == []
    assert _processes(tmp_path) == []


def test_admin_tem_rota_html_e_json_leitura_sem_acionar_ia() -> None:
    client = TestClient(create_admin_app())
    page = client.get("/system")
    assert page.status_code == 200
    assert 'href="/system"' in page.text
    assert "Saúde do Servidor" in page.text
    assert "Temperatura CPU" in page.text
    assert "Máquina" in page.text
    assert "/static/js/system.js" in page.text
    script = client.get("/static/js/system.js").text
    assert "fetch('/system/state'" in script
    assert "textContent" in script
    assert "Cache-Control" in page.headers

    state = client.get("/system/state")
    assert state.status_code == 200
    assert state.headers["cache-control"] == "no-store"
    assert state.headers["x-content-type-options"] == "nosniff"
    payload = state.json()
    assert set(payload) == {
        "sampled_at", "cpu", "memory", "disk", "uptime_seconds",
        "temperatures", "services", "processes", "sampling_seconds",
    }
    assert not any(field in payload for field in ("environment", "commands", "audio", "transcripts"))
    assert payload["cpu"]["logical_cores"] >= 1
    assert isinstance(payload["services"], list)
    assert client.post("/system/state").status_code == 405
