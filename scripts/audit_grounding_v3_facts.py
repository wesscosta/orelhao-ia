"""Avalia atributos factuais das claims arquivadas sem mudar modelos nem gates."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from orelhao.services.knowledge.fact_evaluation import audit_fact_validation, save_audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Auditoria Fact Validator V3")
    parser.add_argument("--tucano", type=Path, required=True)
    parser.add_argument("--qwen", type=Path, required=True)
    parser.add_argument("--index", type=Path, default=Path("knowledge/index"))
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 10, 29))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = {}
    for name, path in (("tucano2", args.tucano), ("qwen35", args.qwen)):
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document.get("results"), list) or len(document["results"]) != 40:
            raise ValueError(f"resultado incompleto: {name}")
        rows[name] = document["results"]
    report = audit_fact_validation(rows, index_dir=args.index, as_of=args.as_of)
    save_audit(args.output, report)
    print("Claims auditadas:", report["checked_claims"])
    print("Chunks ausentes:", len(report["missing_chunks"]))
    print("Estados:", report["categories"])
    print("Salvo em:", args.output)


if __name__ == "__main__":
    main()
