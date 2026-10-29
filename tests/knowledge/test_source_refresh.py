from pathlib import Path

from orelhao.services.knowledge.loader import load_documents


def test_updated_senac_pi_sources_are_indexable_and_traceable() -> None:
    sources = Path(__file__).resolve().parents[2] / "knowledge" / "sources"
    docs = {document.source: document for document in load_documents(sources)}
    expected = {
        "unidades/rede-senac-piaui.md",
        "cursos/informatica-basica-2026.md",
        "cursos/excel-2026.md",
        "cursos/excel-avancado-2026.md",
        "atendimento/canais-institucionais.md",
        "psg/vagas-e-editais.md",
    }
    assert expected <= docs.keys()
    for source in expected:
        doc = docs[source]
        assert doc.metadata["authority"] == "primary"
        assert doc.metadata["temporal"] is True
        assert str(doc.metadata["retrieved_at"]) == "2026-10-29"
        assert doc.metadata["source_url"].startswith("https://")
        assert len(doc.text) >= 250
    assert "Esperantina" in docs["unidades/rede-senac-piaui.md"].text
    assert "Santa Filomena" in docs["unidades/rede-senac-piaui.md"].text
    assert "437 vagas" in docs["psg/vagas-e-editais.md"].text
    assert "não é o número de vagas atualmente disponíveis" in docs["psg/vagas-e-editais.md"].text



def test_basic_computing_hours_are_per_offering_not_universal() -> None:
    root = Path(__file__).resolve().parents[2] / "knowledge" / "sources"
    doc = {d.source: d for d in load_documents(root)}["cursos/informatica-basica-2026.md"]
    assert "140 horas e de 80 horas" in doc.text
    assert "80 horas em Picos" in doc.text
    assert "não presumir um preço ou carga horária únicos" in doc.text
