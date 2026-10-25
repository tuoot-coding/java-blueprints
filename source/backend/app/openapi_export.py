"""Экспорт OpenAPI-контракта в contracts/openapi.json: `python -m app.openapi_export`.

С флагом --check файл не перезаписывается, а код возврата 1 означает,
что контракт устарел относительно кода.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.application import create_app
from app.core.config import BACKEND_ROOT

DEFAULT_CONTRACT_PATH = BACKEND_ROOT.parent / "contracts" / "openapi.json"


def build_openapi_document() -> dict[str, Any]:
    return create_app().openapi()


def render_openapi_document(document: dict[str, Any]) -> str:
    """Стабильное представление для diff: сортировка ключей, LF, финальный перевод строки."""
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args(argv)
    output_path: Path = arguments.output

    rendered = render_openapi_document(build_openapi_document())
    if arguments.check:
        current = output_path.read_text(encoding="utf-8") if output_path.exists() else None
        if current != rendered:
            sys.stderr.write(f"OpenAPI-контракт устарел: {output_path}\n")
            return 1
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
