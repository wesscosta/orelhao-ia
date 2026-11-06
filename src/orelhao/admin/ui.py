"""Shell visual e componentes HTML do painel administrativo.

Renderização no servidor, sem dependências novas: todo texto variável passa por
``html.escape``. CSS, JavaScript, fonte e ícones são servidos localmente em
``/static`` para manter o painel utilizável sem internet.
"""
from __future__ import annotations

import hashlib
import html
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

STATIC_DIR = Path(__file__).with_name("static")


def _asset_version() -> str:
    """Hash curto do conteúdo de static/: muda a URL dos assets a cada alteração."""
    digest = hashlib.sha256()
    for path in sorted(STATIC_DIR.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(STATIC_DIR).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:10]


ASSET_VERSION = _asset_version()

Tone = Literal["neutral", "info", "ok", "warn", "bad", "live"]


@dataclass(frozen=True)
class NavItem:
    href: str
    label: str
    key: str


@dataclass(frozen=True)
class NavGroup:
    label: str
    icon: str
    items: tuple[NavItem, ...]


NAVIGATION: tuple[NavGroup, ...] = (
    NavGroup("Visão geral", "i-overview", (NavItem("/overview", "Central de operações", "overview"),)),
    NavGroup("Atendimento ao vivo", "i-phone", (NavItem("/monitor", "Monitor da ligação", "monitor"),)),
    NavGroup("Conhecimento", "i-book", (
        NavItem("/", "Fontes e índice", "sources"),
        NavItem("/audit/faq", "FAQ supervisionado", "faq"),
        NavItem("/workbench", "Bancada de testes", "workbench"),
    )),
    NavGroup("Diagnóstico", "i-pulse", (
        NavItem("/audit/audio", "Áudio e microfone", "audio"),
        NavItem("/system", "Máquina", "system"),
    )),
    NavGroup("Administração", "i-shield", (
        NavItem("/audit", "Auditoria e backups", "audit"),
    )),
)


def e(value: object) -> str:
    """Escape para conteúdo e atributos HTML."""
    return html.escape(str(value), quote=True)


def icon(name: str, *, label: str | None = None, size: int = 20) -> str:
    aria = f'role="img" aria-label="{e(label)}"' if label else 'aria-hidden="true"'
    return (f'<svg class="icon" width="{size}" height="{size}" {aria} focusable="false">'
            f'<use href="/static/icons.svg?v={ASSET_VERSION}#{e(name)}"></use></svg>')


def _nav(active: str | None) -> str:
    groups = []
    for group in NAVIGATION:
        links = []
        for item in group.items:
            current = ' aria-current="page"' if item.key == active else ""
            links.append(f'<li><a href="{item.href}"{current}>{e(item.label)}</a></li>')
        is_active = any(item.key == active for item in group.items)
        groups.append(
            f'<li class="nav-group{" is-active" if is_active else ""}">'
            f'<span class="nav-group-label">{icon(group.icon)}{e(group.label)}</span>'
            f'<ul>{"".join(links)}</ul></li>'
        )
    return "".join(groups)


def render_page(
    title: str,
    body: str,
    *,
    active: str | None = None,
    section: str | None = None,
    scripts: tuple[str, ...] = (),
    lede: str | None = None,
    actions: str = "",
) -> str:
    """Página completa com navegação lateral, cabeçalho e área principal."""
    script_tags = "".join(
        f'<script src="/static/js/{e(name)}?v={ASSET_VERSION}" defer></script>'
        for name in ("shell.js", *scripts)
    )
    crumb = f'<p class="page-section">{e(section)}</p>' if section else ""
    lede_html = f'<p class="page-lede">{e(lede)}</p>' if lede else ""
    actions_html = f'<div class="page-actions">{actions}</div>' if actions else ""
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{e(title)} — Orelhão IA</title>
<script>document.documentElement.classList.add('js')</script>
<link rel="preload" href="/static/fonts/atkinson-hyperlegible-400.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/static/css/tokens.css?v={ASSET_VERSION}">
<link rel="stylesheet" href="/static/css/layout.css?v={ASSET_VERSION}">
<link rel="stylesheet" href="/static/css/components.css?v={ASSET_VERSION}">
{script_tags}
</head>
<body>
<a class="skip-link" href="#conteudo">Pular para o conteúdo</a>
<div class="app">
  <header class="topbar">
    <a class="brand" href="/overview">
      <span class="brand-mark" aria-hidden="true">{icon("i-phone", size=18)}</span>
      <span class="brand-text"><strong>Orelhão IA</strong><span>Lumi · Senac Piauí</span></span>
    </a>
    <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="menu-principal">
      {icon("i-menu")}<span>Menu</span>
    </button>
  </header>
  <nav class="sidebar" id="menu-principal" aria-label="Menu principal">
    <ul class="nav">{_nav(active)}</ul>
    <p class="sidebar-note">Acesso local ou por túnel SSH. Não exponha este painel na internet.</p>
  </nav>
  <main id="conteudo" class="main" tabindex="-1">
    <header class="page-header">
      <div>{crumb}<h1>{e(title)}</h1>{lede_html}</div>
      {actions_html}
    </header>
    {body}
  </main>
</div>
</body>
</html>"""


# --- Componentes ---------------------------------------------------------

_TONE_ICON = {"info": "i-info", "ok": "i-check", "warn": "i-alert", "bad": "i-error",
              "neutral": "i-info", "live": "i-phone"}


def badge(text: str, tone: Tone = "neutral", *, attrs: str = "") -> str:
    """Rótulo de estado; o texto sempre carrega o significado, não só a cor."""
    return f'<span class="badge badge-{tone}"{attrs}>{e(text)}</span>'


def alert(message: str, tone: Tone = "info", *, title: str | None = None,
          role: str | None = None, raw: bool = False) -> str:
    content = message if raw else e(message)
    heading = f"<strong>{e(title)}</strong> " if title else ""
    role_attr = f' role="{role}"' if role else (' role="alert"' if tone == "bad" else "")
    return (f'<div class="alert alert-{tone}"{role_attr}>{icon(_TONE_ICON[tone])}'
            f"<div>{heading}{content}</div></div>")


def empty_state(title: str, message: str, *, action: str = "") -> str:
    return (f'<div class="empty"><p class="empty-title">{e(title)}</p>'
            f"<p>{e(message)}</p>{action}</div>")


def panel(title: str, content: str, *, id: str | None = None, aside: str = "",
          level: int = 2, cls: str = "") -> str:
    title_id = f"{id}-titulo" if id else None
    labelled = f' aria-labelledby="{title_id}"' if title_id else ""
    id_attr = f' id="{id}"' if id else ""
    heading_id = f' id="{title_id}"' if title_id else ""
    head_aside = f'<div class="panel-aside">{aside}</div>' if aside else ""
    return (f'<section class="panel {cls}"{id_attr}{labelled}>'
            f'<div class="panel-head"><h{level}{heading_id}>{e(title)}</h{level}>{head_aside}</div>'
            f"{content}</section>")


def stat(label: str, value: str, *, hint: str = "", id: str | None = None,
         tone: Tone = "neutral") -> str:
    id_attr = f' id="{id}"' if id else ""
    hint_html = f'<p class="stat-hint">{e(hint)}</p>' if hint else ""
    return (f'<div class="stat stat-{tone}"><p class="stat-label">{e(label)}</p>'
            f'<p class="stat-value"{id_attr}>{e(value)}</p>{hint_html}</div>')
