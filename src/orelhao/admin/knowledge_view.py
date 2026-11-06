"""Telas de Conhecimento › Fontes e índice (renderização no servidor)."""
from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import quote

from .source_manager import MAX_SOURCE_BYTES, SourceFile
from .ui import Tone, alert, badge, e, empty_state, panel, render_page, stat

SECTION = "Conhecimento"

_STATUS_TONE: dict[str, Tone] = {
    "indexado": "ok", "novo": "info", "alterado": "warn", "ignorado": "neutral",
}


def _size(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    return f"{value / 1024:,.1f} KiB".replace(",", "X").replace(".", ",").replace("X", ".")


def sources_page(
    files: Sequence[SourceFile],
    statuses: dict[str, str],
    manifest: dict[str, object],
    *,
    stale: bool,
    notice: str | None = None,
) -> str:
    pending = sum(1 for status in statuses.values() if status in ("novo", "alterado"))
    rows = "".join(
        f"<tr><td class='wrap'><a href='/edit/{quote(item.relative_path)}'>"
        f"{e(item.relative_path)}</a></td>"
        f"<td class='num'>{_size(item.size_bytes)}</td>"
        f"<td>{badge(statuses[item.relative_path], _STATUS_TONE.get(statuses[item.relative_path], 'neutral'))}</td></tr>"
        for item in files
    )
    table = (
        "<div class='table-wrap' tabindex='0' role='region' aria-labelledby='fontes-titulo'>"
        "<table><thead><tr><th scope='col'>Arquivo</th><th scope='col' class='num'>Tamanho</th>"
        f"<th scope='col'>Situação no índice</th></tr></thead><tbody>{rows}</tbody></table></div>"
        "<p class='note section-gap'>Arquivos de controle e de avaliação ficam fora do índice "
        "de propósito. Salvar uma fonte não reindexa automaticamente: revise as alterações "
        "e reindexe uma vez no final.</p>"
        if files else empty_state(
            "Nenhuma fonte cadastrada",
            "Crie um documento Markdown ou envie um arquivo para começar a base.",
        )
    )
    if not manifest:
        freshness = alert("O índice ainda não foi gerado. Reindexe para que o Lumi consulte "
                          "as fontes.", "warn", title="Índice desatualizado.")
    elif stale:
        freshness = alert(
            f"{pending} fonte(s) nova(s) ou alterada(s) ainda não estão no índice. "
            "O Lumi continua respondendo com a versão anterior até a reindexação.",
            "warn", title="Índice desatualizado.")
    else:
        freshness = alert("Todas as fontes indexáveis estão no índice em uso.", "ok",
                          title="Índice atualizado.", role="status")
    notice_html = alert(notice, "ok", role="status") if notice else ""
    stats = (
        "<div class='stats'>"
        + stat("Fontes", str(len(files)), hint="arquivos em knowledge/sources")
        + stat("Documentos indexados", str(manifest.get("documents", 0)) if manifest else "—")
        + stat("Trechos (chunks)", str(manifest.get("chunks", 0)) if manifest else "—")
        + "</div>"
    )
    add_forms = f"""
<form method="post" action="/create" class="stack">
  <h3>Criar documento</h3>
  <div class="field"><label for="new-title">Título</label>
    <input id="new-title" name="title" required placeholder="FAQ geral" autocomplete="off"></div>
  <div class="field"><label for="new-filename">Nome do arquivo <span class="muted">(opcional)</span></label>
    <input id="new-filename" name="filename" placeholder="faq.md" autocomplete="off" spellcheck="false"
      aria-describedby="new-filename-hint">
    <span class="field-hint" id="new-filename-hint">Se vazio, o nome é gerado a partir do título.</span></div>
  <div class="field"><label for="new-tags">Tags <span class="muted">(opcional, separadas por vírgula)</span></label>
    <input id="new-tags" name="tags" placeholder="faq, atendimento" autocomplete="off"></div>
  <button class="btn btn-primary" type="submit">Criar e editar</button>
</form>
<hr class="divider">
<form method="post" action="/upload" enctype="multipart/form-data" class="stack">
  <h3>Enviar arquivo</h3>
  <div class="field"><label for="up-file">Arquivo Markdown ou TXT</label>
    <input id="up-file" type="file" name="file" accept=".md,.txt" required aria-describedby="up-hint">
    <span class="field-hint" id="up-hint">UTF-8, até {MAX_SOURCE_BYTES // 1024 // 1024} MiB. TXT é convertido para Markdown.</span></div>
  <div class="field"><label for="up-title">Título <span class="muted">(opcional)</span></label>
    <input id="up-title" name="title" placeholder="Título do documento" autocomplete="off"></div>
  <div class="field"><label for="up-tags">Tags <span class="muted">(opcional)</span></label>
    <input id="up-tags" name="tags" placeholder="faq, atendimento" autocomplete="off"></div>
  <button class="btn" type="submit">Enviar e editar</button>
</form>"""
    actions = (
        "<form method='post' action='/reindex' data-busy='Reindexando…'>"
        "<button class='btn btn-primary' type='submit'>Reindexar base</button></form>"
    )
    body = (
        notice_html + freshness + stats
        + "<div class='grid-split section-gap'>"
        + panel("Fontes", table, id="fontes")
        + panel("Adicionar fonte", add_forms, id="adicionar")
        + "</div>"
    )
    return render_page(
        "Fontes e índice", body, active="sources", section=SECTION, actions=actions,
        lede="Documentos que o Lumi consulta para responder. A interface altera somente "
             "knowledge/sources/; o índice só muda quando você reindexa.",
    )


def edit_page(relative_path: str, content: str, *, saved: bool = False) -> str:
    notice = alert("Alterações salvas. Reindexe a base para que o Lumi use a nova versão.",
                   "ok", role="status") if saved else ""
    body = f"""{notice}
<section class="panel" aria-labelledby="editor-titulo">
  <div class="panel-head"><h2 id="editor-titulo"><code>{e(relative_path)}</code></h2></div>
  <form method="post" action="/save" data-busy="Salvando…" data-guard>
    <input type="hidden" name="relative_path" value="{e(relative_path)}">
    <div class="field"><label for="content">Conteúdo em Markdown</label>
      <textarea id="content" class="code" name="content" required spellcheck="true"
        aria-describedby="content-hint">{e(content)}</textarea>
      <span class="field-hint" id="content-hint">Salvar não reindexa. Assim você pode revisar
      várias fontes antes de reconstruir o índice.</span></div>
    <div class="btn-row">
      <button class="btn btn-primary" type="submit">Salvar alterações</button>
      <a class="btn" href="/">Voltar às fontes</a>
      <a class="btn btn-danger" href="/delete/{quote(relative_path)}">Excluir documento…</a>
    </div>
  </form>
</section>"""
    return render_page("Editar fonte", body, active="sources", section=SECTION)


def confirm_delete_page(relative_path: str) -> str:
    body = f"""
<section class="panel" aria-labelledby="excluir-titulo">
  <div class="panel-head"><h2 id="excluir-titulo">Excluir <code>{e(relative_path)}</code>?</h2></div>
  {alert("O arquivo é removido de knowledge/sources/. O índice fica desatualizado até a próxima reindexação. Não há lixeira: guarde uma cópia se precisar recuperar o conteúdo.", "warn")}
  <form method="post" action="/delete" class="btn-row">
    <input type="hidden" name="relative_path" value="{e(relative_path)}">
    <button class="btn btn-danger btn-solid" type="submit">Excluir definitivamente</button>
    <a class="btn" href="/edit/{quote(relative_path)}">Cancelar</a>
  </form>
</section>"""
    return render_page("Excluir fonte", body, active="sources", section=SECTION)


def reindex_page(stats: dict[str, int]) -> str:
    body = (
        alert("O Lumi passa a consultar a versão nova das fontes.", "ok",
              title="Índice atualizado.", role="status")
        + "<div class='stats'>"
        + stat("Documentos", str(stats.get("documents", 0)))
        + stat("Trechos (chunks)", str(stats.get("chunks", 0)))
        + "</div><p class='section-gap'><a class='btn' href='/'>Voltar às fontes</a></p>"
    )
    return render_page("Índice atualizado", body, active="sources", section=SECTION)
