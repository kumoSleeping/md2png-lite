from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    script = Path(__file__).resolve().parent / "scripts" / "render_font_routes.py"
    sys.argv[0] = str(script)
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
