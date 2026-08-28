from __future__ import annotations

import html
import json
import os
import threading
from pathlib import Path
from time import perf_counter
from typing import Annotated
from urllib.parse import quote

from orelhao.config import AppConfig, load_config
from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.interfaces.voice.resample import resample_pcm16, trim_silence_pcm16
from orelhao.runtime_paths import resolve_project_path
from orelhao.services.knowledge.index import build_index
from orelhao.services.knowledge.loader import load_documents
from orelhao.services.knowledge.observation import (
    LocalLLMAnswerGenerator,
    ObservationWorkbench,
    build_default_observation_workbench,
)
from orelhao.services.knowledge.paths import KnowledgePaths, default_knowledge_paths
from orelhao.services.llm.service import LLMService, LocalOpenAICompatibleLLMService
from orelhao.services.stt.service import FasterWhisperSTTService, STTService
from orelhao.services.tts.service import PiperTTSService, TTSService

try:
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
except ImportError:  # pacote base continua utilizável sem o extra [admin]
    FastAPI = File = Form = HTTPException = UploadFile = None
    HTMLResponse = JSONResponse = RedirectResponse = Response = None

from .source_manager import (
    MAX_SOURCE_BYTES,
    atomic_write_source,
    create_markdown_source,
    delete_source,
    list_sources,
    normalize_uploaded_text,
    read_source,
)


def _require_web() -> None:
    if FastAPI is None:
        raise RuntimeError(
            "Interface web não instalada. Execute: pip install -e '.[admin]'"
        )


def _layout(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} — Orelhão IA</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 1080px; margin: 2rem auto; padding: 0 1rem; color: #1f2937; }}
header {{ display:flex; justify-content:space-between; align-items:center; gap:1rem; }}
nav a {{ margin-left:1rem; }}
.card {{ border:1px solid #d1d5db; border-radius:10px; padding:1rem; margin:1rem 0; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:1rem; }}
input, textarea, select {{ width:100%; box-sizing:border-box; padding:.65rem; margin:.3rem 0 .8rem; }}
textarea {{ min-height:420px; font-family:ui-monospace,monospace; }}
button {{ padding:.65rem 1rem; cursor:pointer; }}
.muted {{ color:#6b7280; }}
.ok {{ color:#047857; }}
.warn {{ color:#b45309; }}
.bad {{ color:#b91c1c; }}
.pill {{ display:inline-block; padding:.2rem .55rem; border-radius:999px; background:#f3f4f6; }}
.evidence {{ white-space:pre-wrap; max-height:220px; overflow:auto; }}
code {{ background:#f3f4f6; padding:.15rem .35rem; border-radius:4px; }}
table {{ width:100%; border-collapse:collapse; }}
th, td {{ text-align:left; padding:.6rem; border-bottom:1px solid #e5e7eb; }}
</style>
</head>
<body>
<header><h1>Orelhão IA — Knowledge Admin</h1><nav><a href="/">Base</a><a href="/workbench">Bancada</a></nav></header>
{body}
</body>
</html>"""


def _manifest(index_dir: Path) -> dict[str, object]:
    path = index_dir / "manifest.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _indexed_sources(manifest: dict[str, object]) -> dict[str, str]:
    sources = manifest.get("sources", {})
    if not isinstance(sources, dict):
        return {}
    return {str(key): str(value) for key, value in sources.items()}


def _current_indexable_sources(sources_dir: Path) -> dict[str, str]:
    """Return exactly the source set represented by the knowledge index."""
    return {
        document.source: str(document.metadata.get("sha256", ""))
        for document in load_documents(sources_dir)
    }


def _source_status(
    relative_path: str,
    sha256: str,
    indexed: dict[str, str],
    current_indexable: dict[str, str],
) -> str:
    if relative_path not in current_indexable:
        return "ignorado"
    indexed_hash = indexed.get(relative_path)
    if indexed_hash is None:
        return "novo"
    if indexed_hash != sha256:
        return "alterado"
    return "indexado"


def _index_is_stale(current_indexable: dict[str, str], manifest: dict[str, object]) -> bool:
    return current_indexable != _indexed_sources(manifest)


def create_admin_app(
    paths: KnowledgePaths | None = None,
    *,
    workbench: ObservationWorkbench | None = None,
    stt: STTService | None = None,
    tts: TTSService | None = None,
    llm: LLMService | None = None,
):
    _require_web()
    resolved = paths or default_knowledge_paths()
    app = FastAPI(title="Orelhão IA Knowledge Admin", docs_url=None, redoc_url=None)
    active_workbench = workbench
    active_stt = stt
    active_tts = tts
    active_llm = llm
    stt_preparation_lock = threading.Lock()
    app.state.stt_preparation = {"status": "idle", "elapsed_ms": None, "error": None}

    def app_config() -> AppConfig:
        path = os.getenv("ORELHAO_CONFIG", "config/development.yaml")
        return load_config(resolve_project_path(path))

    def get_workbench() -> ObservationWorkbench:
        nonlocal active_workbench
        if active_workbench is None:
            active_workbench = build_default_observation_workbench(
                resolved.index,
                answer_generator=LocalLLMAnswerGenerator(get_llm()),
            )
        return active_workbench

    def get_llm() -> LLMService:
        nonlocal active_llm
        if active_llm is None:
            active_llm = LocalOpenAICompatibleLLMService(app_config().llm)
        return active_llm

    def get_stt() -> STTService:
        nonlocal active_stt
        if active_stt is None:
            active_stt = FasterWhisperSTTService(app_config().stt)
        return active_stt

    def get_tts() -> TTSService:
        nonlocal active_tts
        if active_tts is None:
            active_tts = PiperTTSService(app_config().tts)
        return active_tts

    def prepare_stt() -> None:
        with stt_preparation_lock:
            if app.state.stt_preparation["status"] != "idle":
                return
            app.state.stt_preparation = {
                "status": "loading",
                "elapsed_ms": None,
                "error": None,
            }

        def load() -> None:
            started = perf_counter()
            try:
                service = get_stt()
                preparer = getattr(service, "prepare", None)
                if callable(preparer):
                    preparer()
            except RuntimeError as exc:
                app.state.stt_preparation = {
                    "status": "error",
                    "elapsed_ms": (perf_counter() - started) * 1000.0,
                    "error": str(exc),
                }
                return
            app.state.stt_preparation = {
                "status": "ready",
                "elapsed_ms": (perf_counter() - started) * 1000.0,
                "error": None,
            }

        threading.Thread(target=load, name="orelhao-stt-prepare", daemon=True).start()

    @app.get("/", response_class=HTMLResponse)
    async def home():
        files = list_sources(resolved.sources)
        manifest = _manifest(resolved.index)
        indexed = _indexed_sources(manifest)
        current_indexable = _current_indexable_sources(resolved.sources)
        rows = "".join(
            f"<tr><td><a href='/edit/{quote(item.relative_path)}'>{html.escape(item.relative_path)}</a></td>"
            f"<td>{item.size_bytes:,} B</td>"
            f"<td>{html.escape(_source_status(item.relative_path, item.sha256, indexed, current_indexable))}</td></tr>"
            for item in files
        ) or "<tr><td colspan='3' class='muted'>Nenhuma fonte cadastrada.</td></tr>"
        stale = _index_is_stale(current_indexable, manifest)
        status = (
            f"{manifest.get('documents', 0)} documentos / {manifest.get('chunks', 0)} chunks"
            if manifest
            else "Índice ainda não gerado"
        )
        freshness = "DESATUALIZADO" if stale else "ATUALIZADO"
        freshness_class = "warn" if stale else "ok"
        body = f"""
<div class="grid">
<section class="card">
<h2>Status</h2>
<p><strong>Fontes:</strong> {len(files)}</p>
<p><strong>Índice:</strong> {html.escape(status)}</p>
<p><strong>Estado:</strong> <span class="{freshness_class}">{freshness}</span></p>
<p class="muted">A interface altera apenas <code>knowledge/sources/</code>.</p>
<form method="post" action="/reindex"><button type="submit">Reindexar base</button></form>
</section>
<section class="card">
<h2>Criar documento</h2>
<form method="post" action="/create">
<label>Nome do arquivo</label><input name="filename" placeholder="faq.md">
<label>Título</label><input name="title" placeholder="FAQ geral" required>
<label>Tags opcionais, separadas por vírgula</label><input name="tags" placeholder="faq, atendimento">
<button type="submit">Criar Markdown</button>
</form>
<hr>
<h2>Enviar arquivo</h2>
<form method="post" action="/upload" enctype="multipart/form-data">
<label>Arquivo Markdown ou TXT</label><input type="file" name="file" accept=".md,.txt" required>
<label>Título opcional</label><input name="title" placeholder="Título do documento">
<label>Tags opcionais, separadas por vírgula</label><input name="tags" placeholder="faq, atendimento">
<button type="submit">Enviar e salvar</button>
</form>
<p class="muted">TXT é normalizado para Markdown. Limite: {MAX_SOURCE_BYTES // 1024 // 1024} MiB.</p>
</section>
</div>
<section class="card"><h2>Fontes</h2><table><thead><tr><th>Arquivo</th><th>Tamanho</th><th>Status</th></tr></thead>
<tbody>{rows}</tbody></table></section>
"""
        return HTMLResponse(_layout("Base de conhecimento", body))

    @app.post("/create")
    async def create(
        filename: str = Form(""),
        title: str = Form(...),
        tags: str = Form(""),
    ):
        try:
            path = create_markdown_source(
                resolved.sources,
                filename=filename,
                title=title,
                tags=tags,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        relative = path.relative_to(resolved.sources).as_posix()
        return RedirectResponse(url=f"/edit/{quote(relative)}", status_code=303)

    @app.post("/upload")
    async def upload(
        file: Annotated[UploadFile, File()],
        title: Annotated[str, Form()] = "",
        tags: Annotated[str, Form()] = "",
    ):
        raw = await file.read(MAX_SOURCE_BYTES + 1)
        if len(raw) > MAX_SOURCE_BYTES:
            raise HTTPException(status_code=413, detail="Arquivo excede 2 MiB")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Arquivo deve estar em UTF-8") from exc
        try:
            name, normalized = normalize_uploaded_text(
                original_name=file.filename or "documento.md",
                raw_text=text,
                title=title,
                tags=tags,
            )
            atomic_write_source(resolved.sources, name, normalized)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(url=f"/edit/{quote(name)}", status_code=303)

    @app.get("/edit/{relative_path:path}", response_class=HTMLResponse)
    async def edit(relative_path: str):
        try:
            content = read_source(resolved.sources, relative_path)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail="Fonte não encontrada") from exc
        body = f"""
<section class="card">
<h2>{html.escape(relative_path)}</h2>
<form method="post" action="/save">
<input type="hidden" name="relative_path" value="{html.escape(relative_path, quote=True)}">
<textarea name="content" required>{html.escape(content)}</textarea>
<button type="submit">Salvar</button>
</form>
<p class="muted">Salvar não reindexa automaticamente. Isso permite revisar várias fontes antes de reconstruir o índice.</p>
<form method="get" action="/delete/{quote(relative_path)}">
<button type="submit">Excluir documento</button>
</form>
</section>
"""
        return HTMLResponse(_layout("Editar fonte", body))

    @app.post("/save")
    async def save(relative_path: str = Form(...), content: str = Form(...)):
        try:
            atomic_write_source(resolved.sources, relative_path, content.rstrip() + "\n")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(url=f"/edit/{quote(relative_path)}", status_code=303)

    @app.get("/delete/{relative_path:path}", response_class=HTMLResponse)
    async def confirm_delete(relative_path: str):
        try:
            read_source(resolved.sources, relative_path)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail="Fonte não encontrada") from exc
        body = f"""
<section class="card">
<h2 class="warn">Confirmar exclusão</h2>
<p>Deseja realmente excluir <strong>{html.escape(relative_path)}</strong>?</p>
<p class="muted">O índice ficará desatualizado até a próxima reindexação.</p>
<form method="post" action="/delete">
<input type="hidden" name="relative_path" value="{html.escape(relative_path, quote=True)}">
<button type="submit">Confirmar exclusão</button>
</form>
<p><a href="/edit/{quote(relative_path)}">Cancelar</a></p>
</section>
"""
        return HTMLResponse(_layout("Excluir fonte", body))

    @app.post("/delete")
    async def remove(relative_path: str = Form(...)):
        try:
            delete_source(resolved.sources, relative_path)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail="Fonte não encontrada") from exc
        return RedirectResponse(url="/", status_code=303)

    @app.post("/reindex", response_class=HTMLResponse)
    async def reindex():
        stats = build_index(resolved.sources, resolved.index)
        body = f"""
<section class="card">
<h2 class="ok">Índice atualizado</h2>
<p>Documentos: <strong>{stats['documents']}</strong></p>
<p>Chunks: <strong>{stats['chunks']}</strong></p>
<p><a href="/">Voltar para a base</a></p>
</section>
"""
        return HTMLResponse(_layout("Índice atualizado", body))

    @app.get("/workbench", response_class=HTMLResponse)
    async def workbench_home():
        prepare_stt()
        body = """
<section class="card">
<h2>Bancada de observação</h2>
<p>Executa retrieval, LLM local e NLI. Nesta fase, o grounding <strong>não bloqueia</strong> a resposta apresentada.</p>
<p id="llm-status" class="muted">Verificando LLM local...</p>
<form method="post" action="/workbench/run">
<label>Pergunta</label>
<textarea id="question" name="question" style="min-height:110px" required></textarea>
<button type="submit" id="run" disabled>Executar teste</button>
<button type="button" id="record" disabled>Preparando STT...</button>
</form>
<p id="voice-status" class="muted">O microfone envia WAV PCM16 para o STT local.</p>
</section>
<script>
const recordButton = document.getElementById('record');
const statusBox = document.getElementById('voice-status');
const runButton = document.getElementById('run');
const llmStatusBox = document.getElementById('llm-status');
let audioContext, processor, source, stream, samples = [], stopTimer;
async function updateLlmStatus() {
  const response = await fetch('/workbench/llm-status');
  const payload = await response.json();
  if (payload.available) {
    runButton.disabled = false;
    llmStatusBox.textContent = `LLM pronta: ${payload.detail}`;
    return;
  }
  llmStatusBox.textContent = `LLM indisponível: ${payload.detail}`;
  setTimeout(updateLlmStatus, 2000);
}
updateLlmStatus();
async function updateSttStatus() {
  const response = await fetch('/workbench/stt-status');
  const payload = await response.json();
  if (payload.status === 'ready') {
    recordButton.disabled = false;
    recordButton.textContent = 'Gravar pergunta';
    statusBox.textContent = `STT pronto; modelo carregado em ${payload.elapsed_ms.toFixed(1)} ms.`;
    return;
  }
  if (payload.status === 'error') {
    statusBox.textContent = `Falha ao carregar STT: ${payload.error}`;
    return;
  }
  setTimeout(updateSttStatus, 1000);
}
updateSttStatus();
async function stopRecording() {
  if (!processor) return;
  clearTimeout(stopTimer);
  processor.disconnect(); source.disconnect();
  stream.getTracks().forEach(track => track.stop());
  const inputRate = audioContext.sampleRate;
  await audioContext.close();
  processor = null;
  recordButton.textContent = 'Gravar pergunta';
  statusBox.textContent = 'Transcrevendo; o primeiro uso também carrega o modelo STT...';
  const wav = encodeWav(resample(concatenate(samples), inputRate, 16000), 16000);
  const form = new FormData();
  form.append('file', wav, 'question.wav');
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 90000);
  try {
    const response = await fetch('/workbench/transcribe', {method: 'POST', body: form, signal: controller.signal});
    const payload = await response.json();
    if (!response.ok) { statusBox.textContent = payload.detail || 'Falha no STT'; return; }
    document.getElementById('question').value = payload.text;
    statusBox.textContent = `Transcrição concluída em ${payload.total_ms.toFixed(1)} ms.`;
  } catch (error) {
    statusBox.textContent = error.name === 'AbortError'
      ? 'O STT excedeu 90 segundos. Aguarde o carregamento do modelo e tente novamente.'
      : `Falha ao enviar áudio: ${error.message}`;
  } finally { clearTimeout(timeout); }
}
recordButton.addEventListener('click', async () => {
  if (processor) {
    await stopRecording();
    return;
  }
  stream = await navigator.mediaDevices.getUserMedia({audio: true});
  audioContext = new AudioContext();
  source = audioContext.createMediaStreamSource(stream);
  processor = audioContext.createScriptProcessor(4096, 1, 1);
  samples = [];
  processor.onaudioprocess = event => samples.push(Array.from(event.inputBuffer.getChannelData(0)));
  source.connect(processor); processor.connect(audioContext.destination);
  stopTimer = setTimeout(stopRecording, 12000);
  recordButton.textContent = 'Parar gravação';
  statusBox.textContent = 'Gravando... parada automática em 12 segundos.';
});
function concatenate(blocks) {
  const length = blocks.reduce((total, block) => total + block.length, 0);
  const output = new Float32Array(length);
  let offset = 0;
  blocks.forEach(block => { output.set(block, offset); offset += block.length; });
  return output;
}
function resample(input, fromRate, toRate) {
  if (fromRate === toRate) return input;
  const ratio = fromRate / toRate, output = new Array(Math.round(input.length / ratio));
  for (let i = 0; i < output.length; i++) {
    const position = i * ratio, left = Math.floor(position), right = Math.min(left + 1, input.length - 1);
    output[i] = input[left] + (input[right] - input[left]) * (position - left);
  }
  return output;
}
function encodeWav(input, sampleRate) {
  const buffer = new ArrayBuffer(44 + input.length * 2), view = new DataView(buffer);
  const write = (offset, value) => [...value].forEach((char, index) => view.setUint8(offset + index, char.charCodeAt(0)));
  write(0, 'RIFF'); view.setUint32(4, 36 + input.length * 2, true); write(8, 'WAVE');
  write(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 1, true); view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  write(36, 'data'); view.setUint32(40, input.length * 2, true);
  input.forEach((sample, index) => view.setInt16(44 + index * 2, Math.max(-1, Math.min(1, sample)) * (sample < 0 ? 32768 : 32767), true));
  return new Blob([view], {type: 'audio/wav'});
}
</script>
"""
        return HTMLResponse(_layout("Bancada de observação", body))

    @app.get("/workbench/stt-status", response_class=JSONResponse)
    async def stt_status():
        return JSONResponse(app.state.stt_preparation)

    @app.get("/workbench/llm-status", response_class=JSONResponse)
    async def llm_status():
        if active_workbench is not None and active_llm is None:
            return JSONResponse(
                {"available": True, "detail": "gerador injetado para teste"}
            )
        service = get_llm()
        checker = getattr(service, "health", None)
        if not callable(checker):
            return JSONResponse({"available": True, "detail": "serviço injetado"})
        health = checker()
        return JSONResponse(
            {"available": health.available, "detail": health.detail}
        )

    @app.post("/workbench/run", response_class=HTMLResponse)
    async def run_workbench(question: str = Form(...)):
        try:
            observation = get_workbench().observe(question)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        decision = observation.grounding
        status_class = "ok" if decision.allows_response else "warn"
        evidence = "".join(
            f"<article class='card'><strong>{html.escape(item.source)}</strong> "
            f"<span class='pill'>retrieval {item.score:.4f}</span>"
            f"<pre class='evidence'>{html.escape(item.text)}</pre></article>"
            for item in observation.evidence
        ) or "<p class='muted'>Nenhum chunk recuperado.</p>"
        body = f"""
<section class="card">
<h2>Resultado</h2>
<p><strong>Pergunta:</strong> {html.escape(observation.question)}</p>
<p><strong>Grounding:</strong> <span class="{status_class}">{decision.status.value.upper()}</span>
<span class="pill">NLI {decision.score:.6f}</span></p>
<p><strong>Gerador:</strong> {html.escape(observation.generator)} · abstenção da geração: {str(observation.generation_abstained).lower()}</p>
<p class="warn"><strong>Modo observação:</strong> a resposta abaixo foi apresentada mesmo quando a política recomenda abstenção.</p>
<h3>Resposta apresentada</h3>
<p>{html.escape(observation.presented_answer)}</p>
<audio controls src="/workbench/speech/{observation.observation_id}?text={quote(observation.presented_answer)}"></audio>
<p class="muted">retrieval={observation.latency.retrieval_ms:.2f} ms · geração={observation.latency.generation_ms:.2f} ms · grounding={observation.latency.grounding_ms:.2f} ms · total={observation.latency.total_ms:.2f} ms</p>
</section>
<section class="card">
<h2>Avaliação humana</h2>
<form method="post" action="/workbench/rate">
<input type="hidden" name="observation_id" value="{observation.observation_id}">
<input type="hidden" name="grounding_status" value="{decision.status.value}">
<select name="rating"><option value="correct">Correta</option><option value="partial">Parcialmente correta</option><option value="incorrect">Incorreta</option></select>
<button type="submit">Registrar avaliação</button>
</form>
</section>
<section><h2>Evidências recuperadas</h2>{evidence}</section>
<p><a href="/workbench">Executar outro teste</a></p>
"""
        return HTMLResponse(_layout("Resultado da bancada", body))

    @app.post("/workbench/rate", response_class=HTMLResponse)
    async def rate_workbench(
        observation_id: str = Form(...),
        rating: str = Form(...),
        grounding_status: str = Form(...),
    ):
        try:
            diagnostic = get_workbench().log.append_rating(
                observation_id,
                rating,
                grounding_status=grounding_status,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        diagnostic_text = {
            "possible_false_positive": "Possível falso positivo do grounding",
            "possible_false_negative": "Possível falso negativo do grounding",
            "aligned": "Avaliação humana alinhada à decisão do grounding",
        }.get(diagnostic, "Avaliação registrada")
        body = f"""
<section class="card"><h2 class="ok">Avaliação registrada</h2>
<p>O evento foi acrescentado ao log sem alterar a observação original.</p>
<p><strong>Diagnóstico:</strong> {html.escape(diagnostic_text)}</p>
<p><a href="/workbench">Voltar à bancada</a></p></section>
"""
        return HTMLResponse(_layout("Avaliação registrada", body))

    @app.post("/workbench/transcribe", response_class=JSONResponse)
    async def transcribe_workbench(file: Annotated[UploadFile, File()]):
        raw = await file.read(20 * 1024 * 1024 + 1)
        if len(raw) > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Áudio excede 20 MiB")
        try:
            started = perf_counter()
            audio = PCM16Audio.from_wav_bytes(raw)
            if audio.channels != 1:
                raise ValueError("Áudio deve ser mono")
            if audio.duration_seconds > 15.0:
                raise ValueError("Gravação deve ter no máximo 15 segundos")
            audio = resample_pcm16(audio, 16_000)
            audio = trim_silence_pcm16(audio)
            if audio.duration_seconds < 0.25:
                raise ValueError("Nenhuma fala foi detectada")
            transcription = get_stt().transcribe(audio)
            if not transcription.text.strip():
                raise ValueError("O STT não reconheceu fala na gravação")
        except (RuntimeError, ValueError, EOFError) as exc:
            raise HTTPException(
                status_code=422,
                detail="Envie WAV PCM16 mono 16 kHz",
            ) from exc
        return JSONResponse(
            {
                "text": transcription.text,
                "elapsed_ms": transcription.elapsed_seconds * 1000.0,
                "total_ms": (perf_counter() - started) * 1000.0,
                "audio_seconds": transcription.audio_seconds,
            }
        )

    @app.get("/workbench/speech/{observation_id}", response_class=Response)
    async def synthesize_workbench(observation_id: str, text: str):
        del observation_id
        try:
            audio = get_tts().synthesize(text)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return Response(content=audio.to_wav_bytes(), media_type="audio/wav")

    return app
