from __future__ import annotations

import argparse


def add_admin_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("admin", help="inicia a interface web local da base")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.set_defaults(handler=_serve)


def _serve(args: argparse.Namespace) -> None:
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit("Interface admin não instalada. Execute: pip install -e '.[admin]'") from exc

    from .app import create_admin_app

    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        print(
            "AVISO: interface sem autenticação. Expor fora do localhost requer "
            "controle de acesso/rede no ambiente."
        )
    uvicorn.run(create_admin_app(), host=args.host, port=args.port, log_level="info")
