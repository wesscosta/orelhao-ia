# Politica de turnos de voz: Orelhao IA

## Regra

O modo fisico do Lumi opera em turnos alternados (*half-duplex*):
a proxima pergunta so e capturada depois que a reproducao da resposta
anterior retorna com sucesso, e nao depois que o LCD termina de rolar.

1. A captura abre o microfone somente em `ESCUTANDO`.
2. Durante STT, RAG e TTS, nao ha uma nova captura de pergunta.
3. `playback.play(...)` e bloqueante: aguarda `pw-play`, `aplay`
   ou o fluxo de audio configurado terminar.
4. `TurnTakingPlayback` serializa todas as reproducoes com lock.
5. Antes de cada nova captura, a politica aguarda o fim da ultima
   reproducao mais **300 ms** de protecao antieco.
6. Se a reproducao falhar, o proximo turno fica bloqueado e o
   atendimento informa erro, sem abrir a captura indevidamente.
7. Se o prazo global do atendimento acabar durante essa espera,
   a captura seguinte nao e iniciada.
8. O LCD continua como saida complementar, sem prolongar os turnos
   pela duracao da rolagem. A proxima escuta cancela a pagina anterior.
9. O gancho do ESP32 (GPIO27) continua encerrando o processo de voz
   independentemente do estado atual.

A saudacao inicial e os avisos de silencio utilizam o mesmo bloqueio.
O pre-aquecimento PipeWire da primeira saudacao e descartado: nao
gera transcricao nem nova pergunta.

## Implementacao

- `src/orelhao/hardware/turn_taking.py`: lock de reproducao e antieco
- `src/orelhao/hardware/voice_worker.py`: encapsula todos os `play`
  e espera a liberacao antes de `capture.capture()`
- `tests/unit/test_voice_turn_taking.py`: espera, concorrencia e falhas
- O firmware ESP32 e a pinagem do LCD nao mudam nesta etapa

## Criterios de verificacao fisica

- Fazer pergunta A; tentar falar B enquanto o Lumi responde: B nao
  deve ser transcrita ou processada.
- Fazer pergunta B depois que A terminou: deve ser capturada.
- O LCD deve mudar para `ESCUTANDO...` no turno seguinte mesmo que a
  resposta A ainda tivesse paginas pendentes.
- Recolocar o monofone durante a resposta: interrompe o atendimento.
- Confirmar o intervalo antieco em microfone real; reduzir ou aumentar
  somente conforme medições de eco/falsos positivos.
