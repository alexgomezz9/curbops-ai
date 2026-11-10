"""Check the demo entry points without contacting providers or changing state."""

import argparse
import json
from urllib.request import urlopen


def read(url: str) -> bytes:
    with urlopen(url, timeout=15) as response:
        return response.read()


def require(condition: bool, description: str) -> None:
    if not condition:
        raise ValueError(description)
    print(f"PASS: {description}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("api_url", nargs="?", default="http://localhost:8000")
    parser.add_argument("--web-url")
    args = parser.parse_args()
    api = args.api_url.rstrip("/")

    health = json.loads(read(f"{api}/health"))
    require(health["status"] == "ok", "API is healthy")

    mission = json.loads(read(f"{api}/api/mission"))
    require(
        mission["simulation"] is True
        and len(mission["vehicles"]) == 3
        and len(mission["deliveries"]) == 15,
        "Mission has 3 simulated vehicles and 15 simulated deliveries",
    )

    scenarios = json.loads(read(f"{api}/api/decision/scenarios"))
    require(
        scenarios["A"]["status"] == "baseline"
        and all(key in scenarios for key in ("B", "C", "generation")),
        "Scenario endpoint returns the baseline and comparison slots",
    )

    if args.web_url:
        require(b"<title>CurbOps AI" in read(args.web_url), "Web entry point serves CurbOps AI")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"Smoke check failed: {exc}") from None
