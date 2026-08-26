# Modelos locais

Não versionar pesos de modelos neste repositório.

Nesta pasta devem ficar apenas manifestos, checksums e instruções de provisionamento.

O modelo de embeddings da v0.6 é provisionado com:

```bash
orelhao knowledge semantic-provision
```

Os pesos permanecem ignorados pelo Git e são necessários somente no provisionamento; o runtime de retrieval é local.

O verificador experimental de evidência da v0.6.0-alpha.4 é provisionado separadamente:

```bash
orelhao knowledge evidence-provision
```

Ele utiliza QA extrativa multilíngue com suporte a casos sem resposta. O artefato ONNX int8
permanece local e não é versionado no repositório.
