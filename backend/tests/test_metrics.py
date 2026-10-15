"""The /metrics endpoint exposes Prometheus metrics.

The endpoint is registered by prometheus-fastapi-instrumentator in
backend/app/main.py. It is scraped by Prometheus (infrastructure
/monitoring/prometheus.yml) and rendered by Grafana. This test pins
the contract: the endpoint exists, responds 200, and contains the
default HTTP instrumentator metric families.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_metrics_endpoint_exists() -> None:
    r = client.get("/metrics")
    assert r.status_code == 200


def test_metrics_endpoint_returns_prometheus_text_format() -> None:
    r = client.get("/metrics")
    body = r.text
    # The Prometheus text exposition format starts every metric family
    # with a HELP or TYPE comment line.
    assert "# HELP" in body or "# TYPE" in body


def test_metrics_contains_http_request_metrics() -> None:
    """After at least one request, the instrumentator exports per-handler
    request counters and latency histograms."""
    # Generate a request so the counter has at least one sample.
    client.get("/health")
    r = client.get("/metrics")
    body = r.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body


def test_metrics_excludes_itself_from_instrumentation() -> None:
    """The /metrics endpoint must not itself be instrumented; otherwise
    every scrape adds a sample and the metric count grows without
    bound."""
    r = client.get("/metrics")
    body = r.text
    # The handler label for the metrics route should not appear.
    assert 'handler="/metrics"' not in body
