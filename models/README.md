# Modelos locais

Não versionar pesos de modelos neste repositório.

Nesta pasta devem ficar apenas manifestos, checksums e instruções de provisionamento.

Os pesos GGUF da LLM também permanecem locais e ignorados pelo Git. A alpha.13 não escolhe nem baixa um modelo automaticamente; ela consome um servidor local compatível com OpenAI. Consulte `docs/llm.md` e mantenha o arquivo em um caminho de implantação como `models/llm/modelo-instruct.gguf`.

O modelo de embeddings da v0.6 é provisionado com:

```bash
orelhao knowledge semantic-provision
```

Os pesos permanecem ignorados pelo Git e são necessários somente no provisionamento; o runtime de retrieval é local.

O verificador experimental de evidência é provisionado separadamente:

```bash
orelhao knowledge evidence-provision
```

Ele utiliza QA extrativa multilíngue com suporte a casos sem resposta. O artefato ONNX int8
permanece local e não é versionado no repositório.

Para a ablação de precisão da alpha.7, o artefato FP32 da mesma revisão pode coexistir com o INT8:

```bash
orelhao knowledge evidence-provision --variant fp32
orelhao knowledge evidence-evaluate --model-variant fp32 --json
```

Os arquivos locais são `model_int8.onnx` e `model_fp32.onnx`. INT8 continua sendo o padrão; nenhum peso deve ser adicionado ao Git.

O candidato de arquitetura da alpha.8 é provisionado em diretório independente:

```bash
orelhao knowledge evidence-provision --model mdeberta-v3
orelhao knowledge evidence-evaluate --model mdeberta-v3 --json
```

O candidato NLI da alpha.9 verifica afirmações contra passagens e também fica isolado:

```bash
orelhao knowledge evidence-provision --model nli-minilm --variant fp32
orelhao knowledge evidence-evaluate \
  knowledge/evaluation/grounding-v1.json \
  --model nli-minilm \
  --model-variant fp32 \
  --diagnostics --json
```

O artefato ONNX não deve ser commitado. O manifesto registra revisão, tamanho e checksum.

Após calibrar somente em `grounding-v1.json`, execute o holdout próprio uma vez por política:

```bash
for policy in nli-balanced nli-conservative; do
  orelhao knowledge evidence-evaluate \
    knowledge/evaluation/grounding-v2-holdout.json \
    --model nli-minilm \
    --model-variant fp32 \
    --threshold-policy "$policy" \
    --diagnostics --json
done
```

A alpha.11 mantém os mesmos pesos e thresholds. O novo `GroundingPolicy` apenas converte o score em `supported`, `unsupported` ou `uncertain`; não há novo provisionamento.

O candidato mDeBERTa-v3 usa somente INT8 nesta etapa. XLM-RoBERTa INT8 permanece padrão até uma comparação completa favorável.

Compare verificadores locais pelo benchmark separado, sem promover automaticamente o modelo:

```bash
orelhao knowledge evidence-evaluate --model-dir models/evidence/candidato --json
```
