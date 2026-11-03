"""Intenções conversacionais estritas para o terminal Senac, sem geração livre.

Respostas institucionais genéricas baseadas em knowledge/sources/institucional/
sobre-o-senac-piaui.md e cursos/agenda-e-unidades.md (base consultada em 2026).
Informações específicas, atualizadas ou indisponíveis permanecem no RAG.
"""
from __future__ import annotations

import platform
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in value if not unicodedata.combining(char))


def _normalize(question: str) -> str:
    value = _fold(question).strip(" ?!.,;:")
    value = re.sub(r"[^\w\s]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return re.sub(r"^(?:ei |ola |oi )?(?:lumi|o lumi)[, :]+", "", value)


def _general_courses_request(normalized: str) -> bool:
    """Escolha explícita do catálogo, sem confundir cursos específicos/preços."""
    return bool(re.fullmatch(
        r"(?:(?:eu |e )?(?:quero|queria|prefiro|desejo|gostaria de) "
        r"(?:(?:saber|conhecer|ver) )?(?:sobre |sobre os |os |dos )?|"
        r"(?:vamos )?(?:saber|falar|conversar) (?:sobre |sobre os |dos |de )?|"
        r"(?:me fale|fale|me diga|diga) (?:sobre |sobre os |os )?|"
        r"(?:os |sobre os )?)"
        r"cursos(?: (?:do|no) senac(?: piaui)?)?",
        normalized,
    ))


def _general_programming_request(normalized: str) -> bool:
    """Reconhece consultas gerais sobre programação, nunca preços/vagas/carga."""
    if re.search(
        r"\b(?:preco|valor|custa|custo|quanto|vagas?|matricula|inscricao|"
        r"horario|carga horaria|duracao|requisito|abert[oa]s?|disponiveis|hoje|"
        r"atualmente)\b", normalized,
    ):
        return False
    return bool(re.fullmatch(
        r"(?:(?:eu |e )?(?:quero|queria|gostaria de|desejo) "
        r"(?:(?:saber|conhecer|ver|falar) )?(?:sobre |de |os )?|"
        r"(?:o senac tem |tem |quais sao os |quais os |os |sobre |area de |"
        r"na area de )?)"
        r"(?:cursos? (?:na area de |de |sobre ))?"
        r"programacao(?: (?:no|do) senac(?: piaui)?)?",
        normalized,
    ))


def looks_like_stt_hallucination(text: str) -> bool:
    """Filtra clichês específicos de geração STT; não tenta corrigir nomes próprios."""
    normalized = _normalize(text)
    if normalized in {
        "transcricao em portugues brasileiro",
        "transcricao em portugues brasileiro pt br",
        "transcricao e legendas",
    }:
        return True
    return (
        normalized.startswith(("transcricao e legendas por ", "transcricao e legendas pela "))
        and len(normalized) < 100
    ) or normalized.count("se inscreva no canal") >= 2


CITIES = {
    "bom jesus": "Bom Jesus",
    "esperantina": "Esperantina",
    "floriano": "Floriano",
    "parnaiba": "Parnaíba",
    "picos": "Picos",
    "pio ix": "Pio IX",
    "piripiri": "Piripiri",
    "santa filomena": "Santa Filomena",
    "sao raimundo nonato": "São Raimundo Nonato",
}
TERESINA_AREAS = {
    "parque piaui": "Parque Piauí",
    "zona sul": "Parque Piauí, na Zona Sul",
    "severino ramos": "Severino Ramos Brasil",
    "zona leste": "Zona Leste",
    "centro": "Centro",
}


def runtime_description(config: Any) -> str:
    """Resumo local e não sensível da configuração efetiva; sem IP ou credenciais."""
    os_name = platform.system()
    cpu = ""
    mem_gb: int | None = None
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if line.startswith("PRETTY_NAME="):
                os_name = line.partition("=")[2].strip('"')[:60]
                break
    except OSError:
        pass
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                cpu = line.partition(":")[2].strip()
                cpu = re.sub(r"\s+", " ", cpu)[:65]
                break
    except OSError:
        pass
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                mem_gb = round(int(line.split()[1]) / (1024 * 1024))
                break
    except (OSError, ValueError, IndexError):
        pass
    stt = getattr(getattr(config, "stt", None), "model", "local")
    hardware = f", com {cpu}" if cpu else ""
    memory = f" e aproximadamente {mem_gb} gigabytes de memória" if mem_gb else ""
    return (
        f"Sou executado localmente no Orelhão IA com {os_name}{hardware}{memory}. "
        f"Uso Whisper {stt} para reconhecer sua fala, um modelo de linguagem local "
        "para formular respostas e Piper para falar. Não tenho acesso a GPS."
    )


@dataclass(frozen=True)
class VoiceIntentReply:
    text: str | None = None
    prompt: str | None = None
    end_session: bool = False

    def __post_init__(self) -> None:
        if (self.text is None) == (self.prompt is None):
            raise ValueError("Informe texto ou prompt, não ambos")
        if self.end_session and self.prompt != "closing":
            raise ValueError("Encerramento por voz exige a despedida controlada")


class VoiceIntentRouter:
    """Estado temporário de uma ligação, limitado a tópicos claramente identificados."""

    def __init__(self, *, runtime_summary: str | None = None) -> None:
        self.awaiting_location = False
        self.awaiting_course_area = False
        self.awaiting_technology_choice = False
        self.awaiting_programming_city = False
        self.awaiting_courses_or_prices = False
        self.awaiting_supervision_kind = False
        self.paused = False
        self.runtime_summary = runtime_summary or (
            "Uso reconhecimento de fala Whisper, um modelo de linguagem local, "
            "uma base de conhecimento controlada e síntese de voz Piper."
        )

    def _location_followup(self, normalized: str) -> VoiceIntentReply:
        self.awaiting_location = False
        for area, display in TERESINA_AREAS.items():
            if re.search(rf"\b{re.escape(area)}\b", normalized):
                return VoiceIntentReply(
                    text=(
                        f"O Senac Piauí lista uma unidade em {display}. "
                        "Não posso garantir que seja a mais próxima sem uma localização mais precisa."
                    )
                )
        if "teresina" in normalized:
            self.awaiting_location = True
            return VoiceIntentReply(
                text=(
                    "Em Teresina, o Senac informa unidades no Centro, Parque Piauí, "
                    "Severino Ramos Brasil e Zona Leste. Qual é seu bairro?"
                )
            )
        for city, display in CITIES.items():
            if re.search(rf"\b{re.escape(city)}\b", normalized):
                return VoiceIntentReply(
                    text=(
                        f"O Senac Piauí lista uma unidade em {display}. "
                        "Para confirmar endereço e distância, consulte o canal oficial."
                    )
                )
        return VoiceIntentReply(
            text="Não consegui identificar a localidade. Informe uma cidade ou bairro do Piauí."
        )

    def route(self, question: str) -> VoiceIntentReply | None:
        normalized = _normalize(question)
        if not normalized:
            return None

        # Encerramento intencional da chamada; nunca consulta o RAG.
        if re.fullmatch(
            r"(?:finaliza|finalizar|finaliza a conversa|pode finalizar|"
            r"pode encerrar|encerra|encerrar|encerrar atendimento|"
            r"encerrar conversa|termina|terminar|tchau|ate logo|"
            r"pode desligar|desliga|quero encerrar|quero finalizar)",
            normalized,
        ):
            return VoiceIntentReply(prompt="closing", end_session=True)

        # Pedidos explícitos de aguardar não são consultas factuais ao RAG.
        if re.fullmatch(
            r"(?:so um instante|um instante|um momento|aguarde (?:um instante|um momento)?"
            r"|espera (?:um pouco|ai|um instante|so um instante)?"
            r"|(?:ah pois |ah |pois )?espera so um instante"
            r"|pera ai|pera um pouco|aguarda ai)",
            normalized,
        ):
            self.paused = True
            return VoiceIntentReply(prompt="ack_wait")
        self.paused = False

        if re.fullmatch(
            r"(?:e |ah |entendi |bom )?(?:esta bem|ta bem|tudo bem|entendi|certo|ok|beleza|eu sei|sei|obrigado|obrigada|valeu|compreendi)",
            normalized,
        ):
            return VoiceIntentReply(prompt="ack_continue")

        # Uma escolha do menu de cursos pode vir depois de "cursos ou preços".
        if _general_courses_request(normalized):
            self.awaiting_courses_or_prices = False
            self.awaiting_course_area = True
            return VoiceIntentReply(prompt="courses_overview")
        if self.awaiting_courses_or_prices:
            self.awaiting_courses_or_prices = False
            if re.fullmatch(
                r"(?:eu )?(?:quero|queria|prefiro|gostaria de) "
                r"(?:(?:saber|conhecer) )?(?:o |os )?"
                r"(?:preco|precos|valor|valores|custo|custos)"
                r"(?: dos cursos)?",
                normalized,
            ) or normalized in {"preco", "precos", "valor", "valores", "o preco"}:
                return VoiceIntentReply(prompt="ask_specific_course")

        # Metaperguntas do produto sempre têm prioridade sobre o contexto do turno.
        if (
            re.search(r"\b(?:quem e|o que e) (?:o |a )?(?:lumi|assistente)\b", normalized)
            or re.fullmatch(r"(?:qual (?:e )?(?:o )?seu nome|se apresente|apresente se)", normalized)
            or re.fullmatch(r"(?:e )?(?:quem e voce|quem voce e|o que voce e|quem e tu)", normalized)
        ):
            return VoiceIntentReply(prompt="who_is_lumi")

        if (
            re.search(r"\b(?:o que|quais coisas) (?:voce |o lumi )?(?:consegue|pode|sabe) "
                      r"(?:me )?(?:fazer|ajudar|responder|informar)\b", normalized)
            or re.search(r"\b(?:quais (?:sao )?(?:suas|as suas) (?:funcoes|capacidades|habilidades)"
                         r"|para que voce serve|como voce pode (?:me )?ajudar)\b", normalized)
            or re.search(r"\b(?:sobre o que voce (?:consegue|pode) fazer"
                         r"|o que voce consegue fazer)\b", normalized)
        ):
            return VoiceIntentReply(prompt="lumi_capabilities")

        if (
            re.search(r"\b(?:qual|quais|me diga|fale|explique|como e|e)\b", normalized)
            and re.search(r"\b(?:sua configuracao|seu hardware|configuracao do lumi"
                          r"|configuracao do orelhao|modelo de ia que voce usa"
                          r"|modelos que voce usa)\b", normalized)
            and not re.search(r"\b(?:igual|mesma|parecida)\b", normalized)
        ):
            return VoiceIntentReply(text=self.runtime_summary)
        if re.search(r"\b(?:sua configuracao|configuracao do lumi)\b", normalized):
            return VoiceIntentReply(prompt="clarify_configuration")

        if re.fullmatch(
            r"(?:onde estou|onde eu estou|qual e minha localizacao"
            r"|qual a minha localizacao|voce sabe onde estou|onde fica aqui)",
            normalized,
        ):
            self.awaiting_location = True
            return VoiceIntentReply(prompt="no_location_access")

        if re.fullmatch(
            r"(?:(?:me diga|me fale|fale|conte|quero saber) )?"
            r"(?:algumas? )?(?:informacoes?|coisas) (?:sobre|a respeito de)"
            r"(?: o que)?",
            normalized,
        ) or normalized in {"me fale sobre", "me diga sobre"}:
            return VoiceIntentReply(prompt="ask_topic")

        if (
            ("senac" in normalized or "instituicao" in normalized)
            and re.search(r"\b(?:informacoes|o que e|fale|me conte|me diga|sobre)\b", normalized)
            and not re.search(r"\b(?:curso|cursos|unidade|matricula|vaga|horario|preco|valor)\b", normalized)
        ):
            return VoiceIntentReply(prompt="about_senac")

        # O termo supervisão é ambíguo, e não há endereços de supervisões no corpus.
        if self.awaiting_supervision_kind:
            self.awaiting_supervision_kind = False
            if re.search(r"\b(?:unidade|centro de educacao|escola)\b", normalized):
                self.awaiting_location = True
                return VoiceIntentReply(prompt="ask_location")
            if "supervisao" in normalized or "setor" in normalized:
                return VoiceIntentReply(prompt="supervision_unverified")
            if normalized in {"senac", "do senac"}:
                self.awaiting_supervision_kind = True
                return VoiceIntentReply(prompt="clarify_supervision")
            # Outra pergunta não deve ser consumida como resposta à clarificação.

        if (
            "supervisao" in normalized
            and re.search(r"\b(?:mais proxima|mais proximo|perto|onde fica)\b", normalized)
        ):
            self.awaiting_supervision_kind = True
            return VoiceIntentReply(prompt="clarify_supervision")

        if self.awaiting_location:
            # Não consumir outra pergunta que não responda com uma localidade.
            mentions_place = (
                "teresina" in normalized
                or any(re.search(rf"\b{re.escape(place)}\b", normalized)
                       for place in (*TERESINA_AREAS, *CITIES))
                or re.match(r"^(?:estou|fica|moro|no bairro|na cidade|em |no |na )", normalized)
            )
            if mentions_place:
                return self._location_followup(normalized)
            self.awaiting_location = False

        if (
            re.search(r"\b(?:senac|unidade)\b", normalized)
            and re.search(r"\b(?:mais proximo|mais proxima|perto de mim|perto daqui)\b", normalized)
        ):
            self.awaiting_location = True
            return VoiceIntentReply(prompt="ask_location")

        # Após o menu de tecnologia, "Programação" é uma escolha válida.
        # A cidade é usada somente para consultar anúncios históricos verificáveis.
        programming_request = _general_programming_request(normalized)
        if self.awaiting_programming_city:
            city = re.sub(
                r"^(?:(?:e|mas) )?(?:(?:na cidade de|quero em|pode ser em|aqui em|em|na|no|para) )?",
                "", normalized,
            )
            if city in {"teresina", "zona leste"}:
                self.awaiting_programming_city = False
                return VoiceIntentReply(prompt="programming_teresina")
            if city == "piripiri":
                self.awaiting_programming_city = False
                return VoiceIntentReply(prompt="programming_piripiri")
            if city in CITIES or city in TERESINA_AREAS:
                self.awaiting_programming_city = False
                return VoiceIntentReply(prompt="programming_city_unverified")
            # Repetir o assunto é permitido; perguntas novas seguem seu fluxo.
            if not programming_request:
                self.awaiting_programming_city = False

        if programming_request:
            self.awaiting_course_area = False
            self.awaiting_technology_choice = False
            self.awaiting_programming_city = True
            return VoiceIntentReply(prompt="programming_area")

        if self.awaiting_technology_choice:
            self.awaiting_technology_choice = False

        if self.awaiting_course_area:
            self.awaiting_course_area = False
            if any(term in normalized for term in (
                'carga horaria', 'preco', 'valor', 'quanto', 'horario',
                'vaga', 'matricula', 'inscricao', 'aberto', 'disponivel',
            )):
                return None
            if re.search(r"\b(?:comercio|comercial|vendas?|gestao|administracao)\b", normalized):
                if re.search(r"\bcursos?\b", normalized):
                    return VoiceIntentReply(prompt="commerce_details")
                self.awaiting_course_area = True
                return VoiceIntentReply(prompt="commerce_area")
            if re.search(r"\b(?:informatica|tecnologia|computadores?|excel)\b", normalized):
                self.awaiting_technology_choice = True
                return VoiceIntentReply(prompt="technology_area")
            if re.search(r"\b(?:idiomas?|linguas?|ingles|espanhol)\b", normalized):
                return VoiceIntentReply(prompt="language_area")
            # Pergunta diferente passa ao RAG, sem forçar uma resposta genérica.

        has_senac = bool(re.search(r"\bsenac\b", normalized))
        has_courses = bool(re.search(r"\bcursos?\b", normalized))
        if (
            has_senac and has_courses
            and re.search(r"\b(?:hoje|agora|atualmente|abertos?|disponiveis|vagas)\b", normalized)
            and not re.search(r"\b(?:excel|informatica|administracao|ingles|espanhol|gestao|comercio)\b", normalized)
        ):
            self.awaiting_course_area = True
            return VoiceIntentReply(prompt="courses_current")
        specialized = bool(re.search(
            r"\b(?:excel|informatica|administracao|ingles|espanhol|comercio"
            r"|vendas?|gestao|gratuitos?|valor|preco|vagas?|matriculas?"
            r"|horario|carga horaria|inscricao|inscricoes)\b", normalized
        ))
        if has_senac and has_courses and not specialized and (
            re.search(r"\b(?:quais?|que|tem|oferece|oferecidos?|oferta|disponiveis"
                      r"|lista|existem|conhecer|mostrar|informar)\b", normalized)
            or re.fullmatch(r"(?:os )?cursos? (?:do|no) senac(?: piaui)?", normalized)
        ):
            self.awaiting_course_area = True
            return VoiceIntentReply(prompt="courses_overview")

        if (
            has_senac and re.search(r"\bcustos?\b", normalized)
            and re.search(r"\b(?:quais?|que|os|sao|tem)\b", normalized)
        ):
            self.awaiting_courses_or_prices = True
            return VoiceIntentReply(prompt="courses_or_prices")

        # Fragmentos curtos não reconhecidos não devem ser enviados como perguntas
        # factuais. Cursos, localidades e solicitações claras continuam no RAG.
        tokens = normalized.split()
        if len(tokens) <= 2 and not re.search(
            r"\b(?:senac|curso|cursos|excel|enfermagem|saude|gestao|comercio|"
            r"tecnologia|idiomas|unidade|preco|valor|matricula|psg)\b",
            normalized,
        ):
            return VoiceIntentReply(prompt="clarify_request")
        return None
