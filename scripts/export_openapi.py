"""
scripts/export_openapi.py
=========================
Exports the FastAPI OpenAPI 3.1 specification to static JSON without booting a live server.
Enables automated TypeScript type generation and client SDK synchronization.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure repository root is in python path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.main import app  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("export_openapi")


def generate_openapi_schema() -> Dict[str, Any]:
    """Generates the canonical OpenAPI schema dictionary from the FastAPI application."""
    schema = app.openapi()
    if not isinstance(schema, dict) or "paths" not in schema:
        raise ValueError("Invalid OpenAPI schema generated from application.")
    return schema


def export_openapi(output_path: Path) -> Path:
    """Generates and writes the OpenAPI JSON file to the designated path."""
    schema = generate_openapi_schema()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, sort_keys=True)
        f.write("\n")

    path_count = len(schema.get("paths", {}))
    component_count = len(schema.get("components", {}).get("schemas", {}))
    log.info(
        "Successfully exported OpenAPI schema to %s (%d endpoints, %d schemas)",
        output_path,
        path_count,
        component_count,
    )
    return output_path


def main() -> None:
    """CLI entrypoint for exporting the OpenAPI specification."""
    parser = argparse.ArgumentParser(
        description="Export Mercury FastAPI OpenAPI specification to static JSON.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=REPO_ROOT / "openapi.json",
        help="Target output path for openapi.json (default: <repo_root>/openapi.json)",
    )
    args = parser.parse_args()
    export_openapi(args.output)


if __name__ == "__main__":
    main()
