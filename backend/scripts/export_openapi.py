"""Write the OpenAPI schema to a file so the frontend client can be generated offline.

uv run python -m scripts.export_openapi ../frontend/lib/api/openapi.json
"""

import json
import sys
from pathlib import Path

from app.main import create_app


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
