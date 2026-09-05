from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from argus.interfaces.web.api import router as api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Argus-PG Mission Control",
        description="Autonomous PostgreSQL Performance & Index Optimization Engine",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def serve_index() -> HTMLResponse:
        html_file = static_dir / "index.html"
        if html_file.exists():
            return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
        return HTMLResponse(
            "<h1>Argus-PG API Running</h1><p>Visit <a href='/docs'>/docs</a> for API documentation.</p>"
        )

    return app
