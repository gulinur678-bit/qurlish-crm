"""FastAPI application assembly. Database schema changes are handled by Alembic."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .auth import router as auth_router
from .catalog_admin import router as catalog_admin_router
from .crm_api import router as crm_router
from .inventory import router as inventory_router


ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Intentionally do not call metadata.create_all here. Use `alembic upgrade head`.
    yield


app = FastAPI(title="Qurlish CRM API", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(inventory_router)
app.include_router(crm_router)
app.include_router(catalog_admin_router)


@app.middleware("http")
async def origin_guard(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method in {"POST", "PATCH", "PUT", "DELETE"}:
        origin = request.headers.get("origin")
        expected = str(request.base_url).rstrip("/")
        if origin and origin.rstrip("/") != expected:
            return Response("Forbidden origin", status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return Response("Forbidden cross-site request", status_code=403)
    response = await call_next(request)
    if request.url.path.startswith(("/api/auth/", "/api/crm/", "/api/admin/")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/staff")
def staff_page():
    return FileResponse(ROOT / "staff.html")


class PublicSiteFiles(StaticFiles):
    allowed_files = {".", "index.html", "app.js", "live.js", "styles.css", "staff.html", "staff.js"}

    async def get_response(self, path: str, scope):
        if path and path not in self.allowed_files:
            raise StarletteHTTPException(status_code=404)
        return await super().get_response(path, scope)


app.mount("/", PublicSiteFiles(directory=ROOT, html=True), name="web")
