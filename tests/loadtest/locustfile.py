"""Locust load test for AeroGrid-XAI.

The endpoint mix models a browser session, not operator traffic. The
Digital Twin view calls /mission/state on mount and on every config
change; that is the dominant request. Supporting endpoints fire once
per navigation. Operator-only routes (/health, /metrics, /status) are
excluded on purpose — including them would average away the latency
that a user actually experiences.

Weights:

    GET  /mission/state?n_uavs=6     50 %   Digital Twin view polls
    GET  /mission/satellites         15 %   satellite picker support
    POST /decisions/charge           15 %   XAI panel re-run
    GET  /design/presets             10 %   Design Studio mount
    POST /discovery/run               5 %   user-initiated discovery
    GET  /saas/whoami                 5 %   auth path verification

Each virtual user reads one token from /tmp/aerogrid-load-tokens.txt
at start (round-robin, one token per user) and uses it for every
request that requires authorization. /discovery/run and /saas/whoami
require a valid token; the others do not.

Run headless with:

    locust -f tests/loadtest/locustfile.py --headless \
           -u 100 -r 10 -t 60s --host http://127.0.0.1:8000

The wrapper script scripts/run_load_test.sh invokes this and asserts
the P95 target on the aggregated response time.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from locust import HttpUser, between, task


_TOKEN_FILE = Path("/tmp/aerogrid-load-tokens.txt")


def _read_tokens() -> list[str]:
    if not _TOKEN_FILE.exists():
        return []
    tokens = [ln.strip() for ln in _TOKEN_FILE.read_text().splitlines() if ln.strip()]
    return tokens


_TOKENS: list[str] = _read_tokens()


_CHARGE_BODY = {
    "candidates": [
        {
            "uav_id": 1,
            "battery_pct": 10,
            "mission_priority": 0.9,
            "network_centrality": 0.7,
            "coverage_contribution": 0.08,
            "workload_urgency": 0.8,
            "thermal_headroom_c": 40,
            "atmospheric_factor": 0.9,
            "beam_alignment": 0.92,
            "transfer_loss": 0.12,
        },
        {
            "uav_id": 2,
            "battery_pct": 55,
            "mission_priority": 0.4,
            "network_centrality": 0.5,
            "coverage_contribution": 0.03,
            "workload_urgency": 0.4,
            "thermal_headroom_c": 45,
            "atmospheric_factor": 0.88,
            "beam_alignment": 0.9,
            "transfer_loss": 0.14,
        },
    ]
}

_DISCOVERY_BODY = {
    "population_size": 8,
    "n_generations": 2,
    "seed": 20261014,
}


class AeroGridUser(HttpUser):
    wait_time = between(0.5, 3.0)

    _next_token_idx: ClassVar[int] = 0

    def on_start(self) -> None:
        # Round-robin assign one token per user.
        if _TOKENS:
            AeroGridUser._next_token_idx = (AeroGridUser._next_token_idx + 1) % len(_TOKENS)
            self._token = _TOKENS[AeroGridUser._next_token_idx]
        else:
            self._token = ""

    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    @task(50)
    def mission_state(self) -> None:
        with self.client.get(
            "/mission/state?n_uavs=6",
            catch_response=True,
            name="GET /mission/state",
        ) as r:
            if r.status_code != 200:
                r.failure(f"status {r.status_code}")

    @task(15)
    def mission_satellites(self) -> None:
        with self.client.get(
            "/mission/satellites",
            catch_response=True,
            name="GET /mission/satellites",
        ) as r:
            if r.status_code != 200:
                r.failure(f"status {r.status_code}")

    @task(15)
    def decision_charge(self) -> None:
        with self.client.post(
            "/decisions/charge",
            json=_CHARGE_BODY,
            catch_response=True,
            name="POST /decisions/charge",
        ) as r:
            if r.status_code != 200:
                r.failure(f"status {r.status_code}")

    @task(10)
    def design_presets(self) -> None:
        with self.client.get(
            "/design/presets",
            catch_response=True,
            name="GET /design/presets",
        ) as r:
            if r.status_code != 200:
                r.failure(f"status {r.status_code}")

    @task(5)
    def discovery_run(self) -> None:
        with self.client.post(
            "/discovery/run",
            json=_DISCOVERY_BODY,
            headers=self._auth(),
            catch_response=True,
            name="POST /discovery/run",
        ) as r:
            if r.status_code not in (200, 401):
                r.failure(f"status {r.status_code}")

    @task(5)
    def whoami(self) -> None:
        with self.client.get(
            "/saas/whoami",
            headers=self._auth(),
            catch_response=True,
            name="GET /saas/whoami",
        ) as r:
            if r.status_code not in (200, 401):
                r.failure(f"status {r.status_code}")
