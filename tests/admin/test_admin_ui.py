"""Shell visual, navegação, ausência de CDN, estados de erro e fluxos FAQ/áudio da UI."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from orelhao.admin.app import create_admin_app
from orelhao.admin.ui import STATIC_DIR
from orelhao.hardware import audio_diagnostics as audio_diag
from orelhao.hardware import faq
from orelhao.hardware.audit import record_event
from orelhao.hardware.live_monitor import start_session
from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.services.knowledge.paths import KnowledgePaths

AUTH = ("admin", "long-local-password-for-tests")
PUBLIC_PAGES = {
    "/overview": "overview", "/": "sources", "/monitor": "monitor",
    "/system": "system", "/workbench": "workbench",
}
ADMIN_PAGES = {"/audit": "audit", "/audit/faq": "faq", "/audit/audio": "audio"}


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> KnowledgePaths:
    monkeypatch.setenv("ORELHAO_AUDIT_ENABLED", "1")
    monkeypatch.setenv("ORELHAO_AUDIT_DB", str(tmp_path / "state" / "audit.sqlite3"))
    monkeypatch.setenv("ORELHAO_MONITOR_DIR", str(tmp_path / "monitor"))
    monkeypatch.setenv("ORELHAO_AUDIT_PASSWORD", AUTH[1])
    monkeypatch.setenv("ORELHAO_AUDIO_DIAGNOSTICS_DIR", str(tmp_path / "private-audio"))
    monkeypatch.delenv("ORELHAO_AUDIO_DIAGNOSTICS_ENABLED", raising=False)
    sources = tmp_path / "knowledge" / "sources"
    sources.mkdir(parents=True)
    (sources / "base.md").write_text("# Instituição\n\nO Senac oferece cursos.\n", encoding="utf-8")
    return KnowledgePaths(sources=sources, index=tmp_path / "knowledge" / "index")


@pytest.fixture
def client(env: KnowledgePaths, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from orelhao.admin import learning_routes

    monkeypatch.setattr(learning_routes, "default_knowledge_paths", lambda: env)
    return TestClient(create_admin_app(paths=env))


def _refusal(session: str = "b" * 24) -> None:
    record_event(session, "voice.transcription", turn=1,
                 text="Quais são os cursos de enfermagem?", status="reconhecida")
    record_event(session, "voice.response", turn=1, status="abstencao", reason="sem_evidencia")


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))


def _parse(text: str) -> list[tuple[str, dict[str, str | None]]]:
    collector = _Collector()
    collector.feed(text)
    return collector.tags


def _all_pages(client: TestClient) -> dict[str, str]:
    pages = {path: client.get(path).text for path in PUBLIC_PAGES}
    pages.update({path: client.get(path, auth=AUTH).text for path in ADMIN_PAGES})
    return pages


def test_every_page_uses_shell_with_current_navigation(client: TestClient) -> None:
    for path, html in _all_pages(client).items():
        key = {**PUBLIC_PAGES, **ADMIN_PAGES}[path]
        tags = _parse(html)
        assert 'class="skip-link" href="#conteudo"' in html, path
        assert '<main id="conteudo"' in html, path
        assert html.count("<h1>") == 1, path
        current = [a for t, a in tags if t == "a" and a.get("aria-current") == "page"]
        assert len(current) == 1, path
        hrefs = {**{v: k for k, v in PUBLIC_PAGES.items()}, **{v: k for k, v in ADMIN_PAGES.items()}}
        assert current[0]["href"] == hrefs[key], path
        assert 'aria-controls="menu-principal"' in html and 'aria-expanded="false"' in html
        assert '<html lang="pt-BR">' in html


def test_navigation_groups_cover_five_areas(client: TestClient) -> None:
    html = client.get("/overview").text
    for area in ("Visão geral", "Atendimento ao vivo", "Conhecimento", "Diagnóstico", "Administração"):
        assert area in html
    for href in ("/overview", "/monitor", "/", "/audit/faq", "/workbench", "/audit/audio", "/system", "/audit"):
        assert f'href="{href}"' in html


def test_form_controls_have_labels(client: TestClient) -> None:
    _refusal()
    row = faq.candidates()[0]
    pages = _all_pages(client)
    pages["faq-selected"] = client.get(
        "/audit/faq", params={"label": row["label"], "topic": row["topic"]}, auth=AUTH).text
    for name, html in pages.items():
        tags = _parse(html)
        label_for = {a.get("for") for t, a in tags if t == "label"}
        for tag, attrs in tags:
            if tag not in ("input", "select", "textarea") or attrs.get("type") == "hidden":
                continue
            if attrs.get("type") == "checkbox":
                continue  # envolvidos pelo <label class="check">
            assert attrs.get("id") in label_for or attrs.get("aria-label"), (name, attrs)


def test_pages_and_assets_work_without_external_cdn(client: TestClient) -> None:
    pattern = re.compile(r"""(?:src|href)=["'](?:https?:)?//""")
    for path, html in _all_pages(client).items():
        assert not pattern.search(html), path
    for asset in sorted(STATIC_DIR.rglob("*")):
        if asset.is_file() and asset.suffix in {".css", ".js", ".svg"}:
            text = asset.read_text(encoding="utf-8")
            assert "http://" not in text.replace("http://www.w3.org/2000/svg", "")
            assert "https://" not in text, asset
    for path, kind in (("/static/css/tokens.css", "text/css"),
                       ("/static/js/shell.js", "javascript"),
                       ("/static/icons.svg", "image/svg+xml"),
                       ("/static/fonts/atkinson-hyperlegible-400.woff2", "font/woff2")):
        response = client.get(path)
        assert response.status_code == 200, path
        assert kind in response.headers["content-type"], path
    assert client.get("/static/../app.py").status_code == 404


def test_scripts_never_inject_event_text_as_html() -> None:
    for name in ("monitor.js", "overview.js", "audit.js", "system.js", "workbench.js", "audio.js", "shell.js"):
        text = (STATIC_DIR / "js" / name).read_text(encoding="utf-8")
        assert "innerHTML" not in text, name
        assert "eval(" not in text, name


def test_overview_is_honest_about_sources(client: TestClient, env: KnowledgePaths) -> None:
    page = client.get("/overview")
    assert page.status_code == 200
    assert "no-store" in page.headers["cache-control"]
    assert 'data-index="missing"' in page.text
    client.post("/reindex")
    assert 'data-index="ok"' in client.get("/overview").text
    (env.sources / "base.md").write_text("# Alterado\n\nNovo texto.\n", encoding="utf-8")
    assert 'data-index="stale"' in client.get("/overview").text
    script = client.get("/static/js/overview.js").text
    for endpoint in ("/monitor/events", "/workbench/llm-status", "/system/state", "/audit/summary?days=7"):
        assert endpoint in script
    assert "Math.random" not in script


def test_admin_pages_still_require_local_auth(client: TestClient) -> None:
    for path in ADMIN_PAGES:
        assert client.get(path).status_code == 401
    assert client.get("/audit/summary").status_code == 401


def test_browser_navigation_errors_are_html_and_api_errors_stay_json(client: TestClient) -> None:
    html_error = client.get("/edit/nao-existe.md", headers={"Accept": "text/html"})
    assert html_error.status_code == 404
    assert "text/html" in html_error.headers["content-type"]
    assert "Fonte não encontrada" in html_error.text
    assert "Voltar e corrigir" in html_error.text
    api_error = client.get("/edit/nao-existe.md")
    assert api_error.json() == {"detail": "Fonte não encontrada"}
    denied = client.get("/audit", headers={"Accept": "text/html"})
    assert denied.status_code == 401
    assert denied.headers["www-authenticate"].startswith("Basic")


def test_source_save_shows_confirmation(client: TestClient) -> None:
    response = client.post("/save", data={"relative_path": "base.md", "content": "# Base\n\nTexto.\n"},
                           follow_redirects=False)
    assert response.headers["location"] == "/edit/base.md?saved=1"
    assert "Alterações salvas" in client.get(response.headers["location"]).text
    assert "Alterações salvas" not in client.get("/edit/base.md").text


def test_faq_table_and_review_panel(client: TestClient) -> None:
    _refusal()
    page = client.get("/audit/faq", auth=AUTH).text
    for column in ("Pergunta agrupada e assunto", "Frequência", "Revisão", "Última ocorrência"):
        assert column in page
    assert "Sem revisão" in page and "Selecione uma pendência" in page
    assert "enfermagem" not in page  # a tabela exibe só o rótulo agrupado, nunca a fala
    row = faq.candidates()[0]
    selected = client.get("/audit/faq", params={"label": row["label"], "topic": row["topic"]},
                          auth=AUTH).text
    assert 'aria-current="true"' in selected
    assert 'action="/audit/faq/review"' in selected
    assert "/audit/faq/publish/" not in selected  # publicação só depois do rascunho salvo


def test_faq_validation_error_preserves_typed_text(client: TestClient) -> None:
    _refusal()
    row = faq.candidates()[0]
    response = client.post("/audit/faq/review", auth=AUTH, data={
        "label": row["label"], "topic": row["topic"],
        "question": "Pergunta válida sobre <enfermagem>?",
        "answer": "Resposta digitada que não pode ser perdida.",
        "source": "http://inseguro.example/",
    })
    assert response.status_code == 422
    assert "text/html" in response.headers["content-type"]
    assert "Resposta digitada que não pode ser perdida." in response.text
    assert "Pergunta válida sobre &lt;enfermagem&gt;?" in response.text
    assert 'aria-invalid="true"' in response.text
    assert faq.reviews() == []


def test_faq_save_then_publish_with_feedback(client: TestClient, env: KnowledgePaths) -> None:
    _refusal()
    row = faq.candidates()[0]
    saved = client.post("/audit/faq/review", auth=AUTH, follow_redirects=False, data={
        "label": row["label"], "topic": row["topic"],
        "question": "Onde consulto as turmas de enfermagem?",
        "answer": "Consulte o catálogo atualizado do Senac Piauí antes da inscrição.",
        "source": "https://pi.senac.br/",
    })
    assert saved.status_code == 303
    target = urlsplit(saved.headers["location"])
    assert parse_qs(target.query)["salvo"] == ["1"]
    page = client.get(target.path + "?" + target.query, auth=AUTH).text
    assert "Rascunho salvo. Nada foi publicado" in page
    review_id = faq.reviews()[0]["id"]
    assert f"/audit/faq/publish/{review_id}" in page
    assert not any(env.sources.rglob("faq-*.md"))
    missing = client.post(f"/audit/faq/publish/{review_id}", auth=AUTH, data={})
    assert missing.status_code == 422
    assert faq.reviews()[0]["status"] == "draft"
    published = client.post(f"/audit/faq/publish/{review_id}", auth=AUTH,
                            data={"confirmed": "1"}, follow_redirects=False)
    assert published.status_code == 303
    assert "publicado=1" in published.headers["location"]
    assert faq.reviews()[0]["status"] == "published"


def test_faq_publish_failure_is_recoverable(
    client: TestClient, env: KnowledgePaths, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _refusal()
    row = faq.candidates()[0]
    review_id = faq.save_review(
        label=row["label"], topic=row["topic"], question="Como consultar os cursos da saúde?",
        answer="Informação confirmada pelo supervisor com fonte pública.",
        source="https://pi.senac.br/",
    )

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Falha simulada de indexação")

    monkeypatch.setattr(faq, "build_index", fail)
    response = client.post(f"/audit/faq/publish/{review_id}", auth=AUTH, data={"confirmed": "1"})
    assert response.status_code == 422
    assert "Publicação cancelada" in response.text and "preservados" in response.text
    assert faq.reviews()[0]["status"] == "draft"
    assert not any(env.sources.rglob("faq-*.md"))


def test_audio_page_states_and_signal(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    page = client.get("/audit/audio", auth=AUTH).text
    assert "Desabilitada" in page and "Não autorizada" in page
    assert re.search(r'<button class="btn btn-primary" type="submit" disabled>Autorizar', page)
    assert "Nenhuma amostra" in page
    disabled = client.post("/audit/audio/arm", auth=AUTH, data={"confirmed": "1"})
    assert disabled.status_code == 422 and "desabilitada" in disabled.text

    monkeypatch.setenv("ORELHAO_AUDIO_DIAGNOSTICS_ENABLED", "1")
    armed = client.post("/audit/audio/arm", auth=AUTH, data={"confirmed": "1"},
                        follow_redirects=False)
    assert armed.headers["location"] == "/audit/audio?autorizado=1"
    page = client.get(armed.headers["location"], auth=AUTH).text
    assert "Próxima sessão autorizada" in page and "Autorizada" in page
    session = start_session()
    diagnostic = type("D", (), {"stop_reason": "silence", "noise_floor": 0.002,
                                "speech_threshold": 0.008, "peak_rms": 0.12})()
    sample = audio_diag.save_sample(session, 1, PCM16Audio(b"\x01\x00" * 16000),
                                    stt_status="recognized", diagnostics=diagnostic)
    assert sample is not None
    page = client.get("/audit/audio", auth=AUTH).text
    assert "Pico RMS 0.1200, piso de ruído 0.0020, limiar 0.0080; pico acima do limiar" in page
    assert f"/audit/audio/sample/{sample}" in page
    assert "silence" in page
    cancelled = client.post("/audit/audio/disarm", auth=AUTH, follow_redirects=False)
    assert cancelled.headers["location"] == "/audit/audio?cancelado=1"


def test_monitor_pipeline_lists_all_stages(client: TestClient) -> None:
    page = client.get("/monitor").text
    steps = re.findall(r'data-step="(\w+)"', page)
    assert steps == ["listen", "stt", "rag", "grounding", "llm", "tts", "play"]
    script = client.get("/static/js/monitor.js").text
    assert "setInterval" not in script  # usa somente o SSE existente


def test_stale_index_after_deletion_explains_removed_sources() -> None:
    from orelhao.admin.knowledge_view import sources_page

    page = sources_page([], {}, {"documents": 1, "chunks": 2}, stale=True)
    assert "Fontes removidas ainda constam no índice." in page
    assert "0 fonte(s)" not in page


def test_workbench_voice_options_come_from_catalog() -> None:
    from orelhao.admin.workbench_view import home_page
    from orelhao.services.tts.voice_catalog import voice_options

    page = home_page()
    for option in voice_options():
        assert f'value="{option.id}"' in page
