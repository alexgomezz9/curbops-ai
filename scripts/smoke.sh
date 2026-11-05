#!/usr/bin/env bash
set -euo pipefail
BASE="${1:-http://localhost:8000}"

echo '[1/3] API health'
curl --max-time 15 -fsS "$BASE/health" | python3 -c 'import json,sys; assert json.load(sys.stdin)["status"] == "ok"'
echo '[2/3] Synthetic mission contract'
curl --max-time 15 -fsS "$BASE/api/mission" | python3 -c 'import json,sys; mission=json.load(sys.stdin); assert mission["simulation"] is True; assert len(mission["vehicles"]) == 3; assert len(mission["deliveries"]) == 15'
echo '[3/3] Scenario comparison contract'
curl --max-time 15 -fsS "$BASE/api/decision/scenarios" | python3 -c 'import json,sys; assert isinstance(json.load(sys.stdin), dict)'
echo 'PASS: read-only API smoke checks; no planning or approval requested'
