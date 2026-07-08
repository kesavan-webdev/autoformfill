"""Paystub (ADP Earnings Statement) PDF parser.

Extracts text via pypdf and uses pattern matching to populate a normalized
JSON shape for the frontend. Targets the ADP layout (e.g. "QUBER INC")
but tolerates minor variations in spacing and labels.
"""
from __future__ import annotations

import io
import re
from typing import Any

from pypdf import PdfReader


_AMOUNT = r"-?\$?[\d,]+\.\d{2}"


def _dedupe(s: str) -> str:
    """Collapse strings that are a whole-number repetition of a shorter prefix.

    Why: pypdf extract_text on ADP paystubs concatenates overlapping text layers,
    producing e.g. "Praveen BojankiPraveen BojankiPraveen BojankiPraveen Bojanki".
    """
    s = s.strip()
    n = len(s)
    if n < 2:
        return s
    for size in range(1, n // 2 + 1):
        if n % size == 0 and s[:size] * (n // size) == s:
            return s[:size].strip()
    return s


def _num(s: str | None) -> float | None:
    if not s:
        return None
    cleaned = s.replace("$", "").replace(",", "").strip()
    if not cleaned or cleaned == "-":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _search(pattern: str, text: str, flags: int = 0) -> str:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else ""


def _extract_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    parts = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(parts)


def _parse_deductions(text: str) -> list[dict[str, Any]]:
    """Find lines between 'Statutory Deductions' header and 'Net Pay'."""
    block = re.search(
        r"Statutory Deductions.*?(?=Net Pay|Deposits|$)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not block:
        return []
    lines = block.group(0).splitlines()
    out: list[dict[str, Any]] = []
    line_re = re.compile(rf"^(.+?)\s+(-?{_AMOUNT})\s+({_AMOUNT})\s*$")
    for line in lines:
        line = line.strip()
        if not line or "this period" in line.lower() or "statutory" in line.lower():
            continue
        m = line_re.match(line)
        if m:
            out.append({
                "label": m.group(1).strip(),
                "thisPeriod": _num(m.group(2)),
                "ytd": _num(m.group(3)),
            })
    return out


def _parse_earnings(text: str) -> list[dict[str, Any]]:
    """Earnings rows live between the 'Earnings' header and 'Gross Pay'."""
    block = re.search(
        r"Earnings\s+rate.*?(?=Gross Pay)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not block:
        return []
    lines = block.group(0).splitlines()
    out: list[dict[str, Any]] = []
    # Row formats vary: "Regular 0.00 5016.00 44664.00" (rate, this, ytd)
    # or "Regular 25.00 80.00 2000.00 24000.00" (rate, hours, this, ytd)
    four_col = re.compile(rf"^(.+?)\s+({_AMOUNT})\s+({_AMOUNT})\s+({_AMOUNT})\s*$")
    five_col = re.compile(
        rf"^(.+?)\s+({_AMOUNT})\s+({_AMOUNT})\s+({_AMOUNT})\s+({_AMOUNT})\s*$"
    )
    for line in lines:
        line = line.strip()
        if not line or line.lower().startswith("earnings"):
            continue
        m5 = five_col.match(line)
        if m5:
            out.append({
                "label": m5.group(1).strip(),
                "rate": _num(m5.group(2)),
                "hours": _num(m5.group(3)),
                "thisPeriod": _num(m5.group(4)),
                "ytd": _num(m5.group(5)),
            })
            continue
        m4 = four_col.match(line)
        if m4:
            out.append({
                "label": m4.group(1).strip(),
                "rate": _num(m4.group(2)),
                "hours": None,
                "thisPeriod": _num(m4.group(3)),
                "ytd": _num(m4.group(4)),
            })
    return out


def _parse_employee(text: str) -> dict[str, str]:
    """Employee block sits between SSN line and the company-address repeat.

    Pattern: 'Social Security Number:XXX-XX-XXXX\n<Name>\n<addr1>\n<addr2?>\n<city, ST zip>'
    """
    m = re.search(
        r"Social Security Number:[^\n]*\n([^\n]+)\n([^\n]+)(?:\n([^\n]+))?\n([^\n]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?)",
        text,
    )
    if not m:
        return {"name": "", "address1": "", "address2": "", "cityStateZip": ""}
    return {
        "name": _dedupe(m.group(1)),
        "address1": _dedupe(m.group(2)),
        "address2": _dedupe(m.group(3) or ""),
        "cityStateZip": _dedupe(m.group(4)),
    }


def _parse_company(text: str) -> dict[str, str]:
    """First non-header lines before 'Earnings Statement' typically hold employer."""
    m = re.search(
        r"Company Code\s*\n([^\n]+)\s*\n(?:Loc/Dept|Number|Page)?[^\n]*\n",
        text,
    )
    code = m.group(1).strip() if m else ""
    # Employer name appears after the header block; pull the first line that
    # looks like an org (uppercase) followed by an address.
    org = re.search(r"\n([A-Z][A-Z0-9 &.,'-]{2,})\n(\d+[^\n]+)\n", text)
    return {
        "code": _dedupe(code),
        "name": _dedupe(org.group(1)) if org else "",
        "address": _dedupe(org.group(2)) if org else "",
    }


def _parse_deposit(text: str) -> dict[str, Any]:
    m = re.search(
        rf"(Checking|Savings)\s+(\S+)\s+(X+\d+)\s+(X+)\s+({_AMOUNT})",
        text,
    )
    if not m:
        return {"accountType": "", "method": "", "account": "", "routing": "", "amount": None}
    return {
        "accountType": m.group(1),
        "method": m.group(2),
        "account": m.group(3),
        "routing": m.group(4),
        "amount": _num(m.group(5)),
    }


def parse_paystub(data: bytes) -> dict[str, Any]:
    text = _extract_text(data)

    period_start = _search(r"Period Starting:\s*([\d/]+)", text)
    period_end = _search(r"Period Ending:\s*([\d/]+)", text)
    pay_date = _search(r"Pay Date:\s*([\d/]+)", text)
    filing_status = _search(r"Taxable Filing Status:\s*([A-Za-z ]+)", text)

    gross_match = re.search(rf"Gross Pay\s+\$?({_AMOUNT})\s+\$?({_AMOUNT})", text)
    gross_this = _num(gross_match.group(1)) if gross_match else None
    gross_ytd = _num(gross_match.group(2)) if gross_match else None

    net_match = re.search(rf"Net Pay\s+\$?({_AMOUNT})", text)
    net_pay = _num(net_match.group(1)) if net_match else None

    federal_taxable = _num(_search(rf"federal taxable wages this period are\s+\$?({_AMOUNT})", text, re.IGNORECASE))

    return {
        "company": _parse_company(text),
        "employee": _parse_employee(text),
        "periodStart": period_start,
        "periodEnd": period_end,
        "payDate": pay_date,
        "filingStatus": filing_status,
        "earnings": _parse_earnings(text),
        "grossPay": gross_this,
        "grossPayYtd": gross_ytd,
        "deductions": _parse_deductions(text),
        "netPay": net_pay,
        "federalTaxableWages": federal_taxable,
        "deposit": _parse_deposit(text),
    }
