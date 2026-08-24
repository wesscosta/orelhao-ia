# Knowledge Admin — v0.4.0-alpha.3

Interface web local para manutenção de `knowledge/sources/`.

## Instalação

```bash
pip install -e '.[admin]'
```

## Execução

```bash
orelhao admin
```

Acesse `http://127.0.0.1:8765`.

Por padrão a interface aceita `.md` e `.txt` UTF-8. TXT é normalizado para Markdown.
O índice continua derivado e é reconstruído explicitamente pelo botão **Reindexar base**
ou pelo comando `orelhao knowledge index`.

## Segurança

A interface não possui autenticação nesta alpha e fica vinculada a `127.0.0.1`.
Não exponha a porta diretamente em redes não confiáveis. A publicação em rede deve
ser feita apenas com controle de acesso/reverse proxy ou política equivalente.
