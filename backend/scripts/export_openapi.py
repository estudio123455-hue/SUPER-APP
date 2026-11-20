"""Exports the unified FastAPI OpenAPI 3.1 contract to shared-contracts/openapi.json."""

import json
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent
MONOREPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402


def export_openapi_schema() -> Path:
    """Generates and writes shared-contracts/openapi.json."""
    contracts_dir = MONOREPO_ROOT / "shared-contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    output_path = contracts_dir / "openapi.json"

    schema = app.openapi()
    output_path.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


if __name__ == "__main__":
    target = export_openapi_schema()
    print(f"Exported OpenAPI 3.1 contract to: {target}")
