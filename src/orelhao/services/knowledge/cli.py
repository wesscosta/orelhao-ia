from __future__ import annotations

import argparse
import time
from pathlib import Path

from orelhao.runtime_paths import resolve_project_path

from .context import ContextBuilder
from .evaluation import evaluate_retriever, evaluate_retriever_detailed, load_evaluation_cases
from .evidence import (
    EVIDENCE_DEFAULT_MODEL,
    EVIDENCE_MODELS,
    EvidenceFilteredRetriever,
    EvidenceVerifier,
    OnnxExtractiveQaEvidenceVerifier,
    OnnxNliEvidenceVerifier,
    evidence_model_directory,
    evidence_model_filename,
    provision_evidence_model,
)
from .evidence_evaluation import (
    EVIDENCE_THRESHOLD_POLICIES,
    evaluate_evidence_verifier,
    load_evidence_evaluation_cases,
)
from .fusion import RRF_RANK_CONSTANT, ReciprocalRankFusionRetriever
from .index import build_index
from .paths import default_knowledge_paths
from .retriever import Retriever
from .semantic import (
    OnnxE5Vectorizer,
    SemanticRetriever,
    build_semantic_index,
    provision_semantic_model,
)
from .vector_retriever import PersistentVectorRetriever


def add_knowledge_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    knowledge = subparsers.add_parser("knowledge", help="gerencia a base de conhecimento local")
    actions = knowledge.add_subparsers(dest="knowledge_command", required=True)

    index = actions.add_parser("index", help="reconstrói o índice a partir de knowledge/sources")
    index.set_defaults(handler=_index)

    semantic_provision = actions.add_parser(
        "semantic-provision",
        help="baixa uma vez o modelo semântico para operação local",
    )
    semantic_provision.set_defaults(handler=_semantic_provision)

    semantic_index = actions.add_parser(
        "semantic-index",
        help="reconstrói os vetores semânticos a partir dos chunks existentes",
    )
    semantic_index.add_argument("--batch-size", type=int, default=8)
    semantic_index.set_defaults(handler=_semantic_index)

    evidence_provision = actions.add_parser(
        "evidence-provision",
        help="baixa uma vez o modelo experimental de verificação de evidência",
    )
    evidence_provision.add_argument(
        "--model",
        choices=tuple(EVIDENCE_MODELS),
        default=EVIDENCE_DEFAULT_MODEL,
        help="arquitetura local a provisionar (padrão: xlm-roberta)",
    )
    evidence_provision.add_argument(
        "--variant",
        choices=tuple({variant for spec in EVIDENCE_MODELS.values() for variant in spec["variants"]}),
        default="int8",
        help="precisão do artefato local (padrão: int8)",
    )
    evidence_provision.set_defaults(handler=_evidence_provision)

    evidence_evaluate = actions.add_parser(
        "evidence-evaluate",
        help="mede answerability diretamente em pares pergunta/chunk pt-BR",
    )
    evidence_evaluate.add_argument(
        "dataset",
        nargs="?",
        type=Path,
        default=resolve_project_path("knowledge/evaluation/evidence-v1.json"),
        help="dataset JSON de answerability (padrão: evidence-v1.json)",
    )
    evidence_evaluate.add_argument(
        "--model",
        choices=tuple(EVIDENCE_MODELS),
        default=EVIDENCE_DEFAULT_MODEL,
        help="arquitetura local a avaliar (padrão: xlm-roberta)",
    )
    evidence_evaluate.add_argument(
        "--model-variant",
        choices=tuple({variant for spec in EVIDENCE_MODELS.values() for variant in spec["variants"]}),
        default="int8",
        help="variante do mesmo modelo ONNX (padrão: int8)",
    )
    threshold_group = evidence_evaluate.add_mutually_exclusive_group()
    threshold_group.add_argument("--threshold", type=float)
    threshold_group.add_argument(
        "--threshold-policy",
        choices=tuple(EVIDENCE_THRESHOLD_POLICIES),
        help="política congelada da alpha.6",
    )
    evidence_evaluate.add_argument(
        "--model-dir",
        type=Path,
        default=None,
        help="diretório local opcional; por padrão deriva de --model",
    )
    evidence_evaluate.add_argument("--diagnostics", action="store_true")
    evidence_evaluate.add_argument("--json", action="store_true", dest="as_json")
    evidence_evaluate.set_defaults(handler=_evidence_evaluate)

    search = actions.add_parser("search", help="consulta o índice local")
    search.add_argument("query", help="pergunta/consulta")
    search.add_argument("--limit", type=int, default=4)
    search.add_argument("--min-score", type=float, default=0.40)
    search.set_defaults(handler=_search)

    evaluate = actions.add_parser("evaluate", help="mede a qualidade do retriever local")
    evaluate.add_argument(
        "dataset",
        nargs="?",
        type=Path,
        default=resolve_project_path("knowledge/evaluation/retrieval-v1.json"),
        help="arquivo JSON com casos de avaliação (padrão: retrieval-v1.json)",
    )
    evaluate.add_argument("--limit", type=int, default=4)
    evaluate.add_argument("--min-score", type=float)
    evaluate.add_argument(
        "--retriever",
        choices=("baseline", "semantic", "fusion", "evidence"),
        default="baseline",
        help="mecanismo medido no mesmo dataset (padrão: baseline)",
    )
    evaluate.add_argument("--json", action="store_true", dest="as_json")
    evaluate.add_argument("--evidence-min-score", type=float, default=0.5)
    evaluate.add_argument(
        "--diagnostics",
        action="store_true",
        help="expõe o resultado de cada caso para diagnóstico de divergências",
    )
    evaluate.set_defaults(handler=_evaluate)


def _index(args: argparse.Namespace) -> None:
    del args
    paths = default_knowledge_paths()
    started = time.perf_counter()
    stats = build_index(paths.sources, paths.index)
    elapsed = time.perf_counter() - started
    print(
        f"Índice atualizado: documents={stats['documents']} | chunks={stats['chunks']} | "
        f"tempo={elapsed:.3f}s"
    )
    print(f"Fonte: {paths.sources}")
    print(f"Índice: {paths.index}")


def _semantic_provision(args: argparse.Namespace) -> None:
    del args
    model_dir = resolve_project_path("models/embeddings/multilingual-e5-small")
    started = time.perf_counter()
    manifest = provision_semantic_model(model_dir)
    elapsed = time.perf_counter() - started
    print(
        f"Modelo semântico provisionado: {manifest['model_id']}@{manifest['revision']} | "
        f"tempo={elapsed:.2f}s"
    )
    print(f"Modelo: {model_dir}")


def _semantic_index(args: argparse.Namespace) -> None:
    paths = default_knowledge_paths()
    model_dir = resolve_project_path("models/embeddings/multilingual-e5-small")
    started = time.perf_counter()
    vectorizer = OnnxE5Vectorizer(model_dir)
    manifest = build_semantic_index(paths.index, vectorizer, batch_size=args.batch_size)
    elapsed = time.perf_counter() - started
    print(
        f"Índice semântico atualizado: chunks={manifest['chunks']} | "
        f"modelo={manifest['model_id']}@{manifest['model_revision']} | tempo={elapsed:.3f}s"
    )
    print(f"Índice: {paths.index}")


def _evidence_provision(args: argparse.Namespace) -> None:
    model_dir = resolve_project_path(
        f"models/evidence/{evidence_model_directory(args.model)}"
    )
    started = time.perf_counter()
    manifest = provision_evidence_model(model_dir, model=args.model, variant=args.variant)
    elapsed = time.perf_counter() - started
    print(
        f"Modelo de evidência provisionado: {manifest['model_id']}@{manifest['revision']} | "
        f"modelo={manifest['model']} | variante={manifest['variant']} | "
        f"tempo={elapsed:.2f}s"
    )
    print(f"Modelo: {model_dir}")


def _evidence_evaluate(args: argparse.Namespace) -> None:
    import json

    paths = default_knowledge_paths()
    cases = load_evidence_evaluation_cases(args.dataset)
    model_dir = args.model_dir or resolve_project_path(
        f"models/evidence/{evidence_model_directory(args.model)}"
    )
    model_spec = EVIDENCE_MODELS[args.model]
    verifier: EvidenceVerifier
    if model_spec["task"] == "nli":
        verifier = OnnxNliEvidenceVerifier(
            model_dir,
            model=args.model,
            variant=args.model_variant,
        )
    else:
        verifier = OnnxExtractiveQaEvidenceVerifier(
            model_dir,
            model=args.model,
            variant=args.model_variant,
        )
    policy = args.threshold_policy or "initial"
    threshold = (
        args.threshold
        if args.threshold is not None
        else EVIDENCE_THRESHOLD_POLICIES[policy]
    )
    report = evaluate_evidence_verifier(
        verifier,
        cases,
        paths.index,
        threshold=threshold,
    )
    payload: dict[str, object] = dict(report.metrics.as_dict())
    payload["threshold"] = threshold
    payload["threshold_policy"] = None if args.threshold is not None else policy
    payload["dataset"] = str(args.dataset)
    payload["model"] = args.model
    payload["task"] = model_spec["task"]
    payload["model_dir"] = str(model_dir)
    payload["model_variant"] = args.model_variant
    model_path = model_dir / evidence_model_filename(args.model_variant, model=args.model)
    payload["model_size_bytes"] = model_path.stat().st_size
    if args.diagnostics:
        payload["results"] = [result.as_dict() for result in report.results]
    payload["category_metrics"] = {
        category: metrics.as_dict()
        for category, metrics in report.category_metrics.items()
    }
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    metrics = report.metrics
    print(f"Casos: {metrics.cases}")
    print(
        f"Classes: respondíveis={metrics.answerable_cases} | "
        f"não respondíveis={metrics.unanswerable_cases}"
    )
    print(f"Acurácia: {metrics.accuracy:.3f}")
    print(f"Acurácia balanceada: {metrics.balanced_accuracy:.3f}")
    print(f"Precisão: {metrics.precision:.3f}")
    print(f"Recall: {metrics.recall:.3f}")
    print(f"Especificidade: {metrics.specificity:.3f}")
    print(f"F1: {metrics.f1:.3f}")
    print(f"ROC AUC: {metrics.roc_auc:.3f}")
    print(f"Latência média: {metrics.mean_latency_ms:.2f}ms")
    print("\nMétricas por categoria:")
    for category, category_result in report.category_metrics.items():
        print(
            f"- {category}: casos={category_result.cases} | "
            f"recall={category_result.recall:.3f} | "
            f"especificidade={category_result.specificity:.3f}"
        )


def _search(args: argparse.Namespace) -> None:
    paths = default_knowledge_paths()
    started = time.perf_counter()
    retriever = PersistentVectorRetriever(paths.index, min_score=args.min_score)
    results = retriever.search(args.query, limit=args.limit)
    elapsed = time.perf_counter() - started
    print(f"Consulta: {args.query}")
    if not results:
        print("Nenhuma evidência suficientemente relevante encontrada.")
        print(f"threshold={args.min_score:.3f} | tempo={elapsed * 1000:.1f}ms")
        return
    context = ContextBuilder().build(args.query, results)
    print(context.text)
    print("\nScores: " + ", ".join(f"{item.score:.3f}" for item in results))
    print(f"tempo={elapsed * 1000:.1f}ms")


def _evaluate(args: argparse.Namespace) -> None:
    import json

    paths = default_knowledge_paths()
    cases = load_evaluation_cases(args.dataset)
    retriever: Retriever
    if args.retriever in {"semantic", "fusion", "evidence"}:
        min_score = 0.0 if args.min_score is None else args.min_score
        if args.retriever in {"fusion", "evidence"} and args.min_score is None:
            min_score = 0.852
        model_dir = resolve_project_path("models/embeddings/multilingual-e5-small")
        semantic_retriever = SemanticRetriever(
            paths.index,
            OnnxE5Vectorizer(model_dir),
            min_score=min_score,
        )
        if args.retriever in {"fusion", "evidence"}:
            fusion_retriever = ReciprocalRankFusionRetriever(
                [
                    PersistentVectorRetriever(paths.index, min_score=0.40),
                    semantic_retriever,
                ]
            )
            if args.retriever == "evidence":
                evidence_dir = resolve_project_path(
                    "models/evidence/xlm-roberta-base-squad2-distilled"
                )
                retriever = EvidenceFilteredRetriever(
                    fusion_retriever,
                    OnnxExtractiveQaEvidenceVerifier(evidence_dir),
                    min_support=args.evidence_min_score,
                )
            else:
                retriever = fusion_retriever
        else:
            retriever = semantic_retriever
    else:
        min_score = 0.40 if args.min_score is None else args.min_score
        retriever = PersistentVectorRetriever(paths.index, min_score=min_score)
    if args.diagnostics:
        report = evaluate_retriever_detailed(retriever, cases, limit=args.limit)
        metrics = report.metrics
    else:
        report = None
        metrics = evaluate_retriever(retriever, cases, limit=args.limit)
    payload: dict[str, object] = dict(metrics.as_dict())
    if args.as_json:
        payload["retriever"] = args.retriever
        payload["min_score"] = min_score
        if args.retriever in {"fusion", "evidence"}:
            payload["baseline_min_score"] = 0.40
            payload["semantic_min_score"] = min_score
            payload["rrf_rank_constant"] = RRF_RANK_CONSTANT
        if args.retriever == "evidence":
            payload["evidence_min_score"] = args.evidence_min_score
        if report is not None:
            payload["results"] = [result.as_dict() for result in report.results]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"Retriever: {args.retriever} | threshold={min_score:.3f}")
    print(f"Casos: {metrics.cases}")
    print(f"Hit@1: {metrics.hit_at_1:.3f}")
    print(f"Hit@{args.limit}: {metrics.hit_at_k:.3f}")
    print(f"MRR: {metrics.mrr:.3f}")
    print(f"Abstenção: {metrics.abstention_accuracy:.3f}")
    print(f"Latência média: {metrics.mean_latency_ms:.2f}ms")
    if report is not None:
        print("\nDiagnóstico por caso:")
        for result in report.results:
            status = "correto" if result.correct else "incorreto"
            returned = ", ".join(
                f"{source} ({score:.3f})"
                for source, score in zip(result.sources, result.scores, strict=True)
            )
            print(f"- [{status}] {result.query}")
            print(f"  retorno: {returned or 'abstenção'}")
