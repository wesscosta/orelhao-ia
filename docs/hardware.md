# Hardware

> **VERIFICAÇÃO — 29/10/2026.** As restrições do Dell de 8 GiB continuam válidas. Não foram realizados ensaios físicos de monofone, gancho, teclado ou boot autônomo até o último commit experimental. Ver [Estado vigente](current-state.md) e [plano de operação](operations.md).

## Decisão vigente — 28/10/2026

A primeira instalação e o piloto do Orelhão IA utilizarão **somente**
o Dell OptiPlex 7050 Micro existente: Intel Core i5-7500T (4 núcleos
e 4 threads), 8 GB DDR4, SSD de aproximadamente 256 GB, GPU Intel HD 630,
sem possibilidade de ampliação de RAM, troca de máquina ou GPU dedicada.

O sistema operacional alvo é **Ubuntu Server 24.04 LTS minimal**, com
Python 3.12 e inferência inicialmente em CPU. Toda escolha de modelo deve
ser aprovada por teste no próprio Dell, sem assumir desempenho a partir
de experiências no computador Arch Linux de desenvolvimento.

Há apenas uma conversa por vez, sem display no MVP. Arduino Uno é o
controlador planejado para teclado 4 × 4 e gancho. Preservar monofone
original e avaliar pinagem, impedância, captura, playback e integração
antes de ligar os conectores eletricamente.

Os critérios de aceitação são groundedness/abstenção, latência de voz,
RSS combinada sem swap sustentado, temperatura com gabinete fechado,
boot autônomo e recuperação de falhas. Consulte
[plano de benchmark](benchmark-optiplex-7050.md).

## Histórico de hardware (substituído)

As propostas anteriores de Mini-PC Core Ultra, Ryzen, 16–32 GB DDR5 ou
GPU dedicada permanecem como histórico de dimensionamento. Elas não
representam possibilidades para esta implantação.
