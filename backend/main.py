"""PDF parsing API — W-9 and ADP-style paystubs."""
from __future__ import annotations

import os
from typing import Any

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from parsers import parse_paystub, parse_paystubs, parse_w9
from renderer import render_paystub_pdf

app = FastAPI(title="Form Parser")

_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
allow_origins = [o.strip() for o in _origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


async def _read_pdf(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a PDF file")
    return await file.read()


@app.post("/parse/w9")
@app.post("/parse")
async def parse_w9_route(file: UploadFile = File(...)) -> dict[str, Any]:
    data = await _read_pdf(file)
    try:
        return parse_w9(data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse PDF: {e}")


@app.post("/parse/paystub")
async def parse_paystub_route(file: UploadFile = File(...)) -> dict[str, Any]:
    data = await _read_pdf(file)
    try:
        return parse_paystub(data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse PDF: {e}")


@app.post("/parse/paystubs")
async def parse_paystubs_route(file: UploadFile = File(...)) -> dict[str, Any]:
    data = await _read_pdf(file)
    try:
        return {"paystubs": parse_paystubs(data)}
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse PDF: {e}")


@app.post("/render/paystub")
async def render_paystub_route(payload: dict[str, Any] = Body(...)) -> Response:
    try:
        pdf = render_paystub_pdf(payload)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to render PDF: {e}")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="paystub.pdf"'},
    )
