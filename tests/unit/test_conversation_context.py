"""Memória curta do monofone: contexto como escopo, jamais como fonte factual."""
from orelhao.hardware.conversation_context import ConversationContext


def test_curso_especifico_resolve_referencia() -> None:
    context = ConversationContext()
    context.remember("Quero saber sobre Excel Avançado", "Informações verificadas")
    outcome = context.resolve("E qual a carga horária?")
    assert outcome.used_context
    assert outcome.reason == "course_entity"
    assert outcome.effective_question == (
        "E qual a carga horária do curso Excel Avançado no Senac Piauí?"
    )
    assert "Informações verificadas" not in outcome.effective_question


def test_sem_curso_identificado_pergunta_qual_curso() -> None:
    context = ConversationContext()
    context.remember("Quais cursos o Senac oferece?", "Várias categorias")
    outcome = context.resolve("E quanto custa?")
    assert outcome.clarification == "Qual curso do Senac você quer consultar?"
    assert outcome.query is None


def test_continuidade_de_cursos_preserva_escopo_institucional() -> None:
    context = ConversationContext()
    context.remember("Quais cursos o Senac oferece?", "Técnicos e livres")
    outcome = context.resolve("E os de gestão?")
    assert outcome.reason == "institution_scope"
    assert "Senac Piauí" in outcome.effective_question


def test_assunto_novo_nao_herda_curso_anterior() -> None:
    context = ConversationContext()
    context.remember("Quais cursos de Excel Avançado existem?", "Excel")
    context.remember("Quem é o Lumi?", "Assistente", reset_topic=True)
    outcome = context.resolve("E quanto custa?")
    assert not outcome.used_context
    assert context.entity is None


def test_diferente_entidade_substitui_referencia_anterior() -> None:
    context = ConversationContext()
    context.remember("Quero saber sobre Excel Avançado", "Sujeito")
    outcome = context.resolve("Qual o valor do curso de Informática Básica?")
    assert not outcome.used_context


def test_memoria_limitada_sem_vazar_conteudo_entre_ligacoes() -> None:
    first = ConversationContext()
    for i in range(9):
        first.remember(f"Turno {i}: Quero cursos de gestão", f"Resposta {i}")
    assert len(first.history) == 4
    assert first.history[0].question.startswith("Turno 5")
    second = ConversationContext()
    assert not second.resolve("E quanto custa?").used_context
    assert not second.history


def test_nao_reutiliza_respostas_anteriores_como_prova() -> None:
    context = ConversationContext()
    context.remember("Quais cursos o Senac oferece?", "O preço é R$ 999.999")
    outcome = context.resolve("E os de gestão?")
    assert "999" not in outcome.effective_question
    assert "do Senac Piauí" in outcome.effective_question
