from __future__ import annotations

import argparse
import time

from .context import ContextBuilder
from .index import build_index
from .paths import default_knowledge_paths
from .vector_retriever import PersistentVectorRetriever


def add_knowledge_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    knowledge = subparsers.add_parser("knowledge", help="gerencia a base de conhecimento local")
    actions = knowledge.add_subparsers(dest="knowledge_command", required=True)

    index = actions.add_parser("index", help="reconstrói o índice a partir de knowledge/sources")
    index.set_defaults(handler=_index)

    search = actions.add_parser("search", help="consulta o índice local")
    search.add_argument("query", help="pergunta/consulta")
    search.add_argument("--limit", type=int, default=4)
    search.add_argument("--min-score", type=float, default=0.40)
    search.set_defaults(handler=_search)


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
