"""W-9 PDF parser API.

Extracts AcroForm field values from an IRS Form W-9 (Rev. March 2024)
and returns them in a normalized JSON shape for the Next.js frontend.
"""
from __future__ import annotations

import io
import re
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader

app = FastAPI(title="W-9 Parser")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mapping from IRS field leaf names (Rev. 3-2024) to our JSON keys.
TEXT_FIELDS: dict[str, str] = {
    "f1_01": "name",
    "f1_02": "businessName",
    "f1_03": "llcClassification",
    "f1_04": "otherClassification",
    "f1_05": "exemptPayeeCode",
    "f1_06": "fatcaCode",
    "f1_07": "address",
    "f1_08": "cityStateZip",
    "f1_09": "requesterNameAddress",
    "f1_10": "accountNumbers",
    "f1_11": "ssn1",
    "f1_12": "ssn2",
    "f1_13": "ssn3",
    "f1_14": "ein1",
    "f1_15": "ein2",
}

# Order of the 7 checkboxes inside the c1_1 group on line 3a.
CLASSIFICATION_BY_INDEX = [
    "individual",
    "c_corp",
    "s_corp",
    "partnership",
    "trust_estate",
    "llc",
    "other",
]

LEAF_RE = re.compile(r"([A-Za-z0-9_]+)(?:\[(\d+)\])?$")


def _leaf(qualified_name: str) -> tuple[str, int]:
    """Return (leaf_name, kid_index). e.g. 'foo.c1_1[3]' -> ('c1_1', 3)."""
    tail = qualified_name.rsplit(".", 1)[-1]
    m = LEAF_RE.match(tail)
    if not m:
        return tail, 0
    return m.group(1), int(m.group(2) or 0)


def _split_city_state_zip(value: str) -> dict[str, str]:
    if not value:
        return {"city": "", "state": "", "zip": ""}
    m = re.match(r"^\s*(.+?),\s*([A-Za-z]{2})\s+(\d{5}(?:-\d{4})?)\s*$", value)
    if m:
        return {"city": m.group(1), "state": m.group(2).upper(), "zip": m.group(3)}
    return {"city": value.strip(), "state": "", "zip": ""}


def _join_tin(parts: list[str]) -> str:
    return "-".join(parts) if any(parts) else ""


def parse_w9(data: bytes) -> dict[str, Any]:
    reader = PdfReader(io.BytesIO(data))
    raw = reader.get_fields() or {}

    flat: dict[str, str] = {}
    classification = ""
    foreign_partners = False

    for qname, field in raw.items():
        if not isinstance(field, dict):
            continue
        leaf, idx = _leaf(qname)
        value = field.get("/V", "")
        if value is None:
            value = ""
        value = str(value)

        if leaf in TEXT_FIELDS:
            flat[TEXT_FIELDS[leaf]] = value
        elif leaf == "c1_1":
            if value and value != "/Off" and 0 <= idx < len(CLASSIFICATION_BY_INDEX):
                classification = CLASSIFICATION_BY_INDEX[idx]
        elif leaf == "c1_2":
            foreign_partners = value not in ("", "/Off")

    csz = _split_city_state_zip(flat.get("cityStateZip", ""))

    return {
        "name": flat.get("name", ""),
        "businessName": flat.get("businessName", ""),
        "classification": classification,
        "llcClassification": flat.get("llcClassification", ""),
        "otherClassification": flat.get("otherClassification", ""),
        "foreignPartners": foreign_partners,
        "exemptPayeeCode": flat.get("exemptPayeeCode", ""),
        "fatcaCode": flat.get("fatcaCode", ""),
        "address": flat.get("address", ""),
        "city": csz["city"],
        "state": csz["state"],
        "zip": csz["zip"],
        "accountNumbers": flat.get("accountNumbers", ""),
        "requesterNameAddress": flat.get("requesterNameAddress", ""),
        "ssn": _join_tin([flat.get("ssn1", ""), flat.get("ssn2", ""), flat.get("ssn3", "")]),
        "ein": _join_tin([flat.get("ein1", ""), flat.get("ein2", "")]),
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/parse")
async def parse(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a PDF file")
    data = await file.read()
    try:
        return parse_w9(data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse PDF: {e}")
