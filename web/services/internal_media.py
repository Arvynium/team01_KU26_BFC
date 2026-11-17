from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import Response

from .internal_asset import INTERNAL_ASSET

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
async def health():
    return {"service": "internal-media", "status": "ready"}


@app.get("/internal/asset")
async def internal_asset():
    return Response(INTERNAL_ASSET, media_type="image/png", headers={"Cache-Control": "no-store"})
