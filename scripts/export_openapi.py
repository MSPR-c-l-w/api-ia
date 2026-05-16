"""
Exporte le schéma OpenAPI dans openapi.json (racine du dépôt).

Usage:
    python scripts/export_openapi.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ENVIRONMENT", "test")

from app.main import app  # noqa: E402

OUTPUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "openapi.json")


def main() -> None:
    schema = app.openapi()
    with open(OUTPUT, "w", encoding="utf-8") as handle:
        json.dump(schema, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(f"OpenAPI exporté : {OUTPUT}")


if __name__ == "__main__":
    main()
