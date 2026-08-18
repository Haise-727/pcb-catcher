"""Launch the inspection station.

    python run.py

Serves the API and, when web/dist exists, the built operator UI from the same
origin. During development run the Vite dev server alongside instead:

    python run.py                 # terminal 1 — API on 127.0.0.1:8000
    cd web && npm run dev         # terminal 2 — UI  on 127.0.0.1:5173
"""

from __future__ import annotations

import uvicorn
from fastapi.staticfiles import StaticFiles

from gerbereye import config
from gerbereye.api import app

DIST = config.ROOT / "web" / "dist"


def main() -> None:
    config.ensure_dirs()

    # Mounted last so it never shadows an /api route. Absent during development,
    # which is why the mount is conditional rather than assumed.
    if DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(DIST), html=True), name="ui")
        print(f"  UI      http://{config.SERVER.host}:{config.SERVER.port}/")
    else:
        print("  UI      not built — run `cd web && npm run dev` for the dev server")

    print(f"  API     http://{config.SERVER.host}:{config.SERVER.port}/api/health")
    print(f"  Stream  http://{config.SERVER.host}:{config.SERVER.port}/stream.mjpg")
    print("  Bound to loopback only; not reachable from the network.\n")

    uvicorn.run(app, host=config.SERVER.host, port=config.SERVER.port, log_level="info")


if __name__ == "__main__":
    main()
