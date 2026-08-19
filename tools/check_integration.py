"""End-to-end integration check — is the whole station actually wired up?

    .venv/bin/python tools/check_integration.py

The unit suite proves each module behaves. This proves the pieces are connected:
it starts the real server on a free port, mounts the built UI exactly as
`run.py` does, and drives every endpoint `web/src/api.js` calls, in the order an
operator would hit them. A green run means a judge can open the browser and the
buttons work.

It exists because the failure it catches is invisible to unit tests: a frontend
calling a path the backend does not serve, or sending a body where the route
wants a query parameter. Both pass every Python test and break the demo.

Run it before any demo or review. Requires demo assets and a seeded board type:

    .venv/bin/python tools/seed_demo.py
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"

results: list[tuple[bool, str, str]] = []


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def call(base: str, path: str, method: str = "GET", body: dict | None = None):
    """Returns (status_code, parsed_or_raw_body)."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        base + path, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        raw, status = exc.read(), exc.code
    except Exception as exc:  # connection refused, timeout
        return 0, str(exc)

    try:
        return status, json.loads(raw)
    except Exception:
        return status, raw


def check(name: str, want: int, got: int, note: str = "") -> None:
    ok = want == got
    results.append((ok, name, note))
    mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
    detail = f"{got}" if ok else f"got {got}, want {want}"
    print(f"  {mark}  {name:<40} {DIM}{detail}{RESET} {note}")


def main() -> int:
    dist = ROOT / "web" / "dist"
    port = free_port()
    base = f"http://127.0.0.1:{port}"

    # Demo mode must be set before the API module binds its camera.
    import os

    os.environ["GERBEREYE_DEMO"] = "1"
    from gerbereye import config
    from gerbereye.api import app

    config.ensure_dirs()
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="ui")

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    for _ in range(100):
        if call(base, "/api/health")[0] == 200:
            break
        time.sleep(0.1)
    else:
        print(f"{RED}server never came up{RESET}")
        return 1

    print(f"\n{DIM}station on {base}{RESET}\n")

    # -- the packaged UI, served same-origin --------------------------------
    print("static UI")
    if dist.is_dir():
        status, body = call(base, "/")
        check("GET / (index.html)", 200, status)
        index = (dist / "index.html").read_text()
        for asset in {p.strip('"') for p in index.split() if "/assets/" in p}:
            asset = asset.split('"')[1] if '"' in asset else asset
            if asset.startswith("/assets/"):
                check(f"GET {asset}", 200, call(base, asset)[0])
    else:
        print(f"  {YELLOW}SKIP{RESET}  web/dist not built — run `cd web && npm run build`")

    # -- health and capture --------------------------------------------------
    print("\nhealth & capture")
    status, health = call(base, "/api/health")
    check("getHealth", 200, status, f"demo_mode={health.get('demo_mode')}")
    status, stability = call(base, "/api/camera/stability?samples=30")
    check("checkStability", 200, status,
          f"{DIM}mean {stability.get('mean_deviation', float('nan')):.2f} levels, "
          f"simulated={stability.get('simulated')}{RESET}")
    check("frame.jpg", 200, call(base, "/api/frame.jpg")[0])

    # -- board types ---------------------------------------------------------
    print("\nboard types")
    status, board_types = call(base, "/api/board-types")
    check("listBoardTypes", 200, status, f"{len(board_types)} defined")
    if not board_types:
        print(f"\n{YELLOW}no board type seeded — run tools/seed_demo.py first{RESET}")
        return 1
    btid = board_types[0]["id"]
    check("components", 200, call(base, f"/api/board-types/{btid}/components")[0])
    check("getThresholds", 200, call(base, f"/api/board-types/{btid}/thresholds")[0])
    check("updateThresholds", 200, call(
        base, "/api/board-types/thresholds", "PATCH",
        {"board_type_id": btid, "min_region_area": 64})[0])
    check("captureGolden", 200, call(
        base, f"/api/board-types/golden?board_type_id={btid}", "POST")[0])

    # -- demo board + virtual bench -----------------------------------------
    print("\ndemo boards & virtual bench")
    check("selectDemoBoard", 200, call(base, "/api/demo/board?index=4", "POST")[0])
    check("nextDemoBoard", 200, call(base, "/api/demo/next-board", "POST")[0])
    for profile in ("unlocked", "harsh", "locked"):
        check(f"benchProfile({profile})", 200,
              call(base, f"/api/bench/profile?name={profile}", "POST")[0])
    check("benchProfile(bogus) rejected", 404,
          call(base, "/api/bench/profile?name=bogus", "POST")[0])

    # The bench is only worth having if it moves the stability gate.
    readings = {}
    for profile in ("locked", "harsh"):
        call(base, f"/api/bench/profile?name={profile}", "POST")
        readings[profile] = call(base, "/api/camera/stability?samples=30")[1]["mean_deviation"]
    gate_works = readings["locked"] < 2.0 < readings["harsh"]
    results.append((gate_works, "bench moves the stability gate", ""))
    print(f"  {GREEN + 'PASS' + RESET if gate_works else RED + 'FAIL' + RESET}  "
          f"{'bench moves the stability gate':<40} "
          f"{DIM}locked {readings['locked']:.2f} < 2.0 < harsh {readings['harsh']:.2f}{RESET}")
    call(base, "/api/bench/profile?name=locked", "POST")
    call(base, "/api/demo/board?index=4", "POST")

    # -- one full inspection cycle -------------------------------------------
    print("\ninspection cycle")
    status, outcome = call(base, f"/api/trigger?board_type_id={btid}", "POST")
    named = sorted({r["ref_des"] for r in outcome.get("regions", []) if r.get("ref_des")})
    check("trigger", 200, status, f"{outcome.get('verdict')}, {named}")
    iid = outcome["inspection_id"]
    rid = outcome["regions"][0]["id"] if outcome.get("regions") else None
    check("listInspections", 200, call(base, "/api/inspections?limit=20")[0])
    check("getInspection", 200, call(base, f"/api/inspections/{iid}")[0])
    if rid is not None:
        check("regionCrop", 200, call(base, f"/api/inspections/{iid}/regions/{rid}.jpg")[0])
        check("overrideRegion", 200, call(
            base, "/api/override", "POST",
            {"region_verdict_id": rid, "revised_verdict": "false_call"})[0])
    check("getTrends", 200, call(base, f"/api/trends?board_type_id={btid}&limit=12")[0])

    # -- records -------------------------------------------------------------
    print("\nrecords & storage")
    check("getStorage", 200, call(base, "/api/storage")[0])
    check("sweepStorage", 200, call(base, "/api/storage/sweep", "POST")[0])
    status, csv_body = call(base, "/api/export.csv")
    rows = csv_body.decode().strip().splitlines() if isinstance(csv_body, bytes) else []
    check("export.csv", 200, status, f"{len(rows) - 1} data rows")

    # -- error contract ------------------------------------------------------
    # The UI renders `detail` verbatim, so these must stay specific enough for
    # an operator to act on rather than a bare status code.
    print("\nerror contract")
    status, body = call(base, "/api/trigger?board_type_id=99999", "POST")
    check("trigger on unknown board type", 503, status, f"{DIM}{body.get('detail')}{RESET}")
    status, body = call(base, "/api/board-types/placement", "POST",
                        {"board_type_id": btid, "content": "not a placement file"})
    check("malformed placement upload", 400, status, f"{DIM}{body.get('detail')}{RESET}")

    failed = [name for ok, name, _ in results if not ok]
    print()
    if failed:
        print(f"{RED}integration: {len(results) - len(failed)} passed, {len(failed)} failed{RESET}")
        for name in failed:
            print(f"  - {name}")
        return 1
    print(f"{GREEN}integration: all {len(results)} checks passed{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
