from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import load_catalog
from .ingest import load_observations
from .vintage import Panel

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_templates.env.autoescape = True


def _parse_origin(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return parsed
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="origin must be YYYY-MM-DD") from exc


def _display_value(value: float) -> str:
    return f"{value:g}"


def create_app() -> FastAPI:
    web_app = FastAPI(title="Brazil macro data")

    @web_app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        return _templates.TemplateResponse(
            request=request, name="index.html", context={}
        )

    @web_app.get("/data", response_class=HTMLResponse)
    def data_view(
        request: Request, origin: str | None = None, series: str | None = None
    ) -> HTMLResponse:
        if origin is not None:
            as_of = _parse_origin(origin)

        observations = load_observations()
        if origin is None:
            if observations.empty:
                raise HTTPException(status_code=400, detail="no curated observations")
            as_of = _parse_origin(str(observations["release_date"].max())[:10])

        catalog = load_catalog()
        if series is None:
            series = next(
                (series_id for series_id, spec in catalog.items() if spec.freq == "M"),
                next(iter(catalog), None),
            )
        if series is None or series not in catalog:
            raise HTTPException(status_code=400, detail="unknown series")

        panel = Panel.build(as_of, observations)
        series_list = []
        for series_id, spec in catalog.items():
            try:
                latest_period, latest_value = panel.latest(series_id)
                period_text = str(latest_period)
                value_text = _display_value(latest_value)
            except KeyError:
                period_text = value_text = "—"
            series_list.append(
                {
                    "id": series_id,
                    "description": spec.description,
                    "freq": spec.freq,
                    "latest_period": period_text,
                    "latest_value": value_text,
                }
            )

        selected_spec = catalog[series]
        try:
            history_series = (
                panel.quarterly(series)
                if selected_spec.freq == "Q"
                else panel.monthly(series)
            )
            history = [
                {"period": str(period), "value": _display_value(value)}
                for period, value in history_series.items()
            ]
        except KeyError:
            history = []

        return _templates.TemplateResponse(
            request=request,
            name="data.html",
            context={
                "origin": as_of.isoformat(),
                "series": series,
                "series_list": series_list,
                "selected_spec": selected_spec,
                "history": history,
            },
        )

    return web_app


app = create_app()
