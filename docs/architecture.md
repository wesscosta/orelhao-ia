# Arquitetura de software

O Orelhão IA é um monólito modular offline-first.

```text
Gancho/MCU -> Core de sessão
                  |
Áudio -> VAD -> STT -> RAG -> LLM -> TTS -> Áudio
```

Camadas:
- `core`: sessão, estados e recursos;
- `services`: STT, RAG, LLM e TTS;
- `interfaces`: voz e extensões de UI;
- `hardware`: gancho, MCU e saúde física;
- `infrastructure`: persistência, telemetria, atualização e logs.

O touch é extensão futura e não integra o escopo do MVP.
