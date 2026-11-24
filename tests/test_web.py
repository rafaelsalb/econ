from __future__ import annotations

import sys
from datetime import date
from types import SimpleNamespace

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from econ import cli, web


def _observations() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "series_id": "monthly_a",
                "ref_date": date(2020, 1, 1),
                "period_end": date(2020, 1, 31),
                "release_date": date(2020, 2, 10),
                "vintage_date": date(2020, 2, 10),
                "value": 1.25,
                "freq": "M",
            },
            {
                "series_id": "monthly_a",
                "ref_date": date(2020, 2, 1),
                "period_end": date(2020, 2, 29),
                "release_date": date(2020, 3, 10),
                "vintage_date": date(2020, 3, 10),
                "value": 9.99,
                "freq": "M",
            },
            {
                "series_id": "quarterly",
                "ref_date": date(2020, 1, 1),
                "period_end": date(2020, 3, 31),
                "release_date": date(2020, 5, 30),
                "vintage_date": date(2020, 5, 30),
                "value": 7.5,
                "freq": "Q",
            },
            {
                "series_id": "quarterly",
                "ref_date": date(2020, 4, 1),
                "period_end": date(2020, 6, 30),
                "release_date": date(2020, 8, 30),
                "vintage_date": date(2020, 8, 30),
                "value": 8.5,
                "freq": "Q",
            },
        ]
    )


def _catalog() -> dict[str, SimpleNamespace]:
    return {
        "monthly_a": SimpleNamespace(freq="M", description="Monthly series", unit="percent"),
        "quarterly": SimpleNamespace(freq="Q", description="Quarterly series", unit="index"),
        "empty_m": SimpleNamespace(freq="M", description="No observations", unit="index"),
    }


def _client(monkeypatch) -> TestClient:
    monkeypatch.setattr(web, "load_observations", _observations)
    monkeypatch.setattr(web, "load_catalog", _catalog)
    return TestClient(web.create_app())


def test_app_factory_and_module_app():
    assert isinstance(web.create_app(), FastAPI)
    assert isinstance(web.app, FastAPI)


def test_home_links_to_data(monkeypatch):
    response = _client(monkeypatch).get("/")
    assert response.status_code == 200
    assert 'href="/data"' in response.text


def test_data_filters_observations_as_of_origin(monkeypatch):
    response = _client(monkeypatch).get(
        "/data", params={"origin": "2020-02-15", "series": "monthly_a"}
    )
    assert response.status_code == 200
    assert "1.25" in response.text
    assert "9.99" not in response.text


def test_data_defaults_to_latest_release_date(monkeypatch):
    response = _client(monkeypatch).get("/data")
    assert response.status_code == 200
    assert "2020-08-30" in response.text
    assert "monthly_a" in response.text


def test_data_shows_em_dash_when_series_has_no_visible_observations(monkeypatch):
    response = _client(monkeypatch).get(
        "/data", params={"origin": "2020-01-01", "series": "empty_m"}
    )
    assert response.status_code == 200
    assert "—" in response.text


def test_data_renders_quarterly_history(monkeypatch):
    response = _client(monkeypatch).get(
        "/data", params={"origin": "2020-06-01", "series": "quarterly"}
    )
    assert response.status_code == 200
    assert "2020Q1" in response.text
    assert "7.5" in response.text
    assert "8.5" not in response.text


def test_data_rejects_malformed_origin(monkeypatch):
    response = _client(monkeypatch).get("/data", params={"origin": "not-a-date"})
    assert response.status_code == 400


def test_data_rejects_unknown_series(monkeypatch):
    response = _client(monkeypatch).get("/data", params={"series": "missing"})
    assert response.status_code == 400


def test_web_cli_parses_defaults_and_options(monkeypatch):
    parsed = []
    monkeypatch.setattr(cli, "cmd_web", lambda args: parsed.append(args))

    monkeypatch.setattr(sys, "argv", ["econ", "web"])
    cli.main()
    monkeypatch.setattr(sys, "argv", ["econ", "web", "--host", "0.0.0.0", "--port", "8123"])
    cli.main()

    assert [(args.host, args.port) for args in parsed] == [
        ("127.0.0.1", 8000),
        ("0.0.0.0", 8123),
    ]


def test_cmd_web_runs_uvicorn_with_configured_host_and_port(monkeypatch):
    calls = []
    monkeypatch.setitem(
        sys.modules,
        "uvicorn",
        SimpleNamespace(run=lambda app, **kwargs: calls.append((app, kwargs))),
    )

    cli.cmd_web(SimpleNamespace(host="localhost", port=9000))

    assert calls == [(web.app, {"host": "localhost", "port": 9000})]
