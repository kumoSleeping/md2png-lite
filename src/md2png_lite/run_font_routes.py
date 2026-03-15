from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "render_font_routes.py"
    sys.argv[0] = str(script)
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
