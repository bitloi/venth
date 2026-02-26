"""Tests for overlay API server (mock client)."""

import sys
import os
import warnings

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from synth_client import SynthClient

from server import app


@pytest.fixture
def client():
    return app.test_client()


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert "mock" in data


def test_edge_daily(client):
    resp = client.get("/api/edge?slug=bitcoin-up-or-down-on-february-26")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "edge_pct" in data
    assert data["signal"] in ("underpriced", "overpriced", "fair")
    assert data["strength"] in ("strong", "moderate", "none")
    assert data["horizon"] == "24h"


def test_edge_missing_slug(client):
    resp = client.get("/api/edge")
    assert resp.status_code == 400


def test_edge_unsupported_slug(client):
    resp = client.get("/api/edge?slug=unsupported-random-market")
    assert resp.status_code == 404


def test_edge_range(client):
    resp = client.get("/api/edge?slug=bitcoin-price-on-february-26")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "edge_pct" in data
    assert "bracket_title" in data
