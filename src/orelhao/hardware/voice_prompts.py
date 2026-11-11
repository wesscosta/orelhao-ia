"""Áudios fixos da experiência de voz, gerados uma vez por configuração Piper.

O arquivo WAV fica num cache local fora do Git. Alterar o modelo ou o
length_scale cria um novo namespace, impedindo reproduzir uma voz desatualizada.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import wave
from pathlib import Path

from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.runtime_paths import resolve_project_path
from orelhao.services.tts.service import PiperTTSService, TTSService

PROMPTS: dict[str, str] = {
    "greeting": "Olá! Eu sou o Lumi. Como posso ajudar?",
    "clarify_request": "Não entendi sua pergunta. Pode repetir?",
    "clarify_configuration": "Você quer saber qual é a minha configuração?",
    "waiting": "Só um instante.",
    "closing": "Até logo!",
    "no_speech": "Não ouvi sua voz. Tente novamente.",
    "idle_check": "Você ainda está aí? Pode falar.",
    "closing_inactivity": "Como não ouvi resposta, vou encerrar. Até logo.",
    "no_transcription": "Não entendi. Pode repetir?",
    "ask_location": "Para encontrar uma unidade próxima, diga sua cidade ou bairro.",
    "courses_overview": (
        "O Senac oferece cursos técnicos, livres e de idiomas. "
        "Minha base inclui Excel e Informática Básica. "
        "Que área você procura?"
    ),
    "courses_or_prices": "Você quer saber os cursos ou o preço de algum curso?",
    "who_is_lumi": (
        "Sou o Lumi, assistente de voz do projeto Orelhão IA. "
        "Ajudo a consultar informações do Senac Piauí pela base de conhecimento local."
    ),
    "lumi_capabilities": (
        "Posso orientar sobre cursos e unidades do Senac Piauí, responder perguntas "
        "que estejam na minha base e informar a data e a hora. "
        "Não faço matrículas nem consulto vagas em tempo real."
    ),
    "about_senac": (
        "O Senac é uma instituição de educação profissional voltada ao comércio, "
        "serviços e turismo. No Piauí, oferece formação profissional e cursos técnicos."
    ),
    "ask_topic": "Claro! Sobre qual assunto você quer informações?",
    "no_location_access": (
        "Não tenho acesso à sua localização. Se disser sua cidade ou bairro, "
        "posso ajudar a identificar unidades do Senac naquela região."
    ),
    "clarify_supervision": (
        "Você procura uma unidade do Senac ou um setor de supervisão?"
    ),
    "supervision_unverified": (
        "Não tenho endereços verificados de setores de supervisão. "
        "Se você procura uma unidade do Senac, posso orientar."
    ),
    "ack_wait": "Tudo bem. Pode falar quando estiver pronto.",
    "ack_continue": "Certo. Pode continuar.",
    "ask_specific_course": "Qual curso do Senac você quer consultar?",
    "clarify_location": (
        "Não consegui entender sua cidade ou bairro. Pode repetir só o nome?"
    ),
    "location_referral": (
        "Ainda não consegui identificar sua localidade. "
        "O atendimento do Senac pode orientar sobre a unidade mais próxima."
    ),
    "abstention_humor": (
        "Essa me pegou! Até um orelhão dos anos 90 tem seus limites. "
        "Não consegui confirmar essa informação. "
        "O pessoal do atendimento do Senac pode ajudar!"
    ),
    "abstention_followup": (
        "Ainda não consegui confirmar essa informação. Quer tentar outra pergunta?"
    ),
    "abstention_admissions": (
        "Não consigo confirmar vagas, preços ou matrículas atualizados. "
        "Para isso, procure o atendimento da unidade do Senac."
    ),
    "abstention_pedagogy": (
        "Não consegui confirmar essa orientação pedagógica. "
        "Procure a supervisão ou a coordenação da sua unidade do Senac."
    ),
    "courses_current": (
        "Posso apresentar categorias e cursos da minha base, mas não confirmar "
        "turmas ou vagas abertas hoje. Que área você procura?"
    ),
    "commerce_details": (
        "Em 2026, o Senac divulgou cursos como Marketing Pessoal e "
        "5S Aplicado à Logística. A oferta atual precisa ser confirmada no portal."
    ),
    "commerce_area": (
        "O Senac Piauí atua em comércio e gestão. "
        "Não tenho a lista de turmas abertas dessa área. "
        "Você pode consultar as ofertas no portal oficial do Senac Piauí."
    ),
    "technology_area": (
        "Tenho informações sobre Informática Básica, Excel e programação. "
        "Qual assunto interessa?"
    ),
    "programming_area": (
        "Em 2026, o Senac anunciou Programação com Minecraft em Teresina e "
        "Parnaíba, e Desenvolvimento de Sistemas em Piripiri. Qual cidade?"
    ),
    "programming_teresina": (
        "Em 2026, o Senac anunciou Programação com Minecraft na Zona Leste "
        "de Teresina, com 40 horas. Confira a oferta atual no portal."
    ),
    "programming_piripiri": (
        "Em 2026, o Senac anunciou Técnico em Desenvolvimento de Sistemas "
        "em Piripiri, com 1200 horas. Confira a oferta atual no portal."
    ),
    "programming_parnaiba": (
        "Em 2026, o Senac anunciou Programação com Minecraft em Parnaíba, "
        "com 40 horas. Consulte o portal para saber sobre turmas atuais."
    ),
    "programming_city_unverified": (
        "Não tenho exemplo de programação verificado para essa cidade. "
        "Isso não significa que não existam cursos. Consulte o catálogo oficial."
    ),
    "language_area": (
        "O Senac Piauí oferece cursos na categoria idiomas. "
        "Para confirmar cursos e turmas atuais, consulte o portal oficial."
    ),
}


class VoicePromptCache:
    """Mantém mensagens estáticas prontas para reprodução, sem reexecutar Piper."""

    def __init__(self, tts: TTSService, cache_dir: Path | None = None) -> None:
        self.tts = tts
        config = getattr(tts, "config", None)
        if config is None or not hasattr(config, "model_dump"):
            # Permite dublês simples nos testes; no servidor usamos cache persistente.
            self.root: Path | None = None
            return
        model_path = resolve_project_path(config.model)
        identity = config.model_dump(mode="json")
        identity.pop("engine", None)  # O mecanismo não altera voz, parâmetros ou frases.
        identity["prompts"] = PROMPTS  # Invalida o cache se algum texto fixo mudar.
        if model_path.is_file():
            stat = model_path.stat()
            identity["model_fingerprint"] = [stat.st_size, stat.st_mtime_ns]
        fingerprint = hashlib.sha256(
            json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:20]
        base = cache_dir or Path(
            os.environ.get(
                "ORELHAO_VOICE_CACHE_DIR",
                str(Path.home() / ".cache" / "orelhao-ia" / "voice"),
            )
        )
        self.root = base / fingerprint

    def audio(self, name: str) -> PCM16Audio:
        if name not in PROMPTS:
            raise KeyError(f"Mensagem de voz desconhecida: {name}")
        target = self.root / f"{name}.wav" if self.root is not None else None
        if target is not None and target.is_file():
            try:
                return PCM16Audio.from_wav_bytes(target.read_bytes())
            except (ValueError, EOFError, OSError, wave.Error):
                pass  # Cache corrompido: gere outra vez, nunca reproduza bytes inválidos.

        audio = self.tts.synthesize(PROMPTS[name])
        if target is None:
            return audio
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{name}-", suffix=".wav", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(audio.to_wav_bytes())
            os.replace(tmp_name, target)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        return audio

    def prewarm(self) -> dict[str, float]:
        """Pré-sintetiza todas as mensagens antes do próximo atendimento."""
        return {name: self.audio(name).duration_seconds for name in PROMPTS}


def main() -> None:
    from orelhao.config import load_config
    from orelhao.runtime_paths import resolve_project_path

    path = os.environ.get("ORELHAO_CONFIG", "config/development.yaml")
    config = load_config(resolve_project_path(path))
    cache = VoicePromptCache(PiperTTSService(config.tts))
    for name, duration in cache.prewarm().items():
        print(f"{name}: {duration:.2f} segundos, salvo em cache")
    print("Cache:", cache.root)


if __name__ == "__main__":
    main()
