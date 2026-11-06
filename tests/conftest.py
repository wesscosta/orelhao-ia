"""Fixtures compartilhadas da suíte."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

FIXTURE_PROFILE = Path(__file__).parent / "fixtures" / "orelhao-server.profile.yaml"


@pytest.fixture
def server_profile_path() -> Path:
    """Perfil do servidor Dell usado nas regressões de áudio/STT.

    Por padrão usa o fixture sanitizado versionado. ``ORELHAO_SERVER_PROFILE``
    permite validar o perfil privado real (por exemplo
    ``config/orelhao-server.qwen.local.yaml``) sem tornar a CI dependente dele.
    """
    override = os.environ.get("ORELHAO_SERVER_PROFILE")
    path = Path(override) if override else FIXTURE_PROFILE
    if not path.is_file():
        pytest.fail(f"Perfil do servidor não encontrado: {path}")
    return path
