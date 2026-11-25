from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

_templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
_templates.env.autoescape = True


def create_console_app(repo: Path | None = None) -> FastAPI:
    """Build the console shell. It keeps ``repo`` for later slices and never touches it."""
    console = FastAPI(title="econ console")
    console.state.repo = repo

    @console.get("/", response_class=HTMLResponse)
    def overview(request: Request) -> HTMLResponse:
        return _templates.TemplateResponse(
            request=request, name="console/overview.html", context={}
        )

    @console.get("/healthz")
    def healthz() -> dict[str, bool]:
        return {"ok": True}

    return console


app = create_console_app()
