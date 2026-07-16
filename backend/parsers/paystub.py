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


_REPEAT_RE = re.compile(r"(.{4,}?)\1+")


def _collapse_repeats(text: str) -> str:
    """Collapse pypdf's overlaid-text duplicates, e.g. 'Gross PayGross Pay...' → 'Gross Pay'.

    Why: pypdf's extract_text() concatenates overlapping text layers on ADP paystubs,
    producing runs like 'Gross Pay $5,016.00$5,016.00$5,016.00$5,016.00 $44,664.00'
    which breaks value regexes that expect a single this-period + a single YTD amount.
    Skip patterns that are a single character repeated (e.g. 'XXXXXXXXX' routing masks)
    so we don't shrink legitimate single-char runs.
    """
    def _sub(m: re.Match) -> str:
        unit = m.group(1)
        if len(set(unit)) == 1:
            return m.group(0)
        return unit
    return _REPEAT_RE.sub(_sub, text)


def _extract_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    parts = [_collapse_repeats(page.extract_text() or "") for page in reader.pages]
    return "\n".join(parts)


def _extract_pages(data: bytes) -> list[str]:
    reader = PdfReader(io.BytesIO(data))
    return [_collapse_repeats(page.extract_text() or "") for page in reader.pages]


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
    # Row formats vary: "Regular 0.00 5016.00 44664.00" (hours, this, ytd; rate blank)
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
                "rate": None,
                "hours": _num(m4.group(2)),
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


def _parse_company(text: str) -> dict[str, Any]:
    """Each header label appears on its own line, followed by its value.

    Text order: `Company Code\n<code>\n<company name>\n<addr...>\nLoc/Dept\n<val>\n
    Number\n<val>\nPage\n<val> Earnings Statement`.
    """
    code = _search(r"Company Code\s*\n([^\n]+)", text)
    loc_dept = _search(r"Loc/Dept\s*\n([^\n]+)", text)
    file_number = _search(r"Number\s*\n([^\n]+)", text)
    page = _search(r"Page\s*\n(\d+\s+of\s+\d+)", text)

    # Company name/address sits between the code value and "Loc/Dept" label.
    block = re.search(
        r"Company Code\s*\n[^\n]+\n(.*?)\nLoc/Dept",
        text,
        re.DOTALL,
    )
    name = ""
    address_lines: list[str] = []
    city_state_zip = ""
    if block:
        raw_lines = [ln.strip() for ln in block.group(1).splitlines() if ln.strip()]
        if raw_lines:
            name = _dedupe(raw_lines[0])
            rest = [_dedupe(ln) for ln in raw_lines[1:]]
            # Last line matching City, ST ZIP is the city/state/zip.
            if rest and re.search(r",\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?", rest[-1]):
                city_state_zip = rest[-1]
                address_lines = rest[:-1]
            else:
                address_lines = rest

    return {
        "code": _dedupe(code),
        "locDept": _dedupe(loc_dept),
        "fileNumber": _dedupe(file_number),
        "page": _dedupe(page),
        "name": name,
        "addressLines": address_lines,
        "cityStateZip": city_state_zip,
    }


def _parse_deposits(text: str) -> list[dict[str, Any]]:
    """Every 'Deposited to the account' row: type, method, account, routing, amount."""
    out: list[dict[str, Any]] = []
    for m in re.finditer(
        rf"(Checking|Savings)\s+(\S+)\s+(X+\d+)\s+(X+)\s+({_AMOUNT})",
        text,
    ):
        out.append({
            "accountType": m.group(1),
            "method": m.group(2),
            "account": m.group(3),
            "routing": m.group(4),
            "amount": _num(m.group(5)),
        })
    return out


def _parse_deposits_summary(text: str) -> list[dict[str, Any]]:
    """The 'Deposits' summary block (account/routing/amount, no type/method)."""
    block = re.search(
        r"Deposits\s*\n\s*account number transit/ABA amount\s*\n(.*?)(?=Important Notes|$)",
        text,
        re.DOTALL,
    )
    if not block:
        return []
    out: list[dict[str, Any]] = []
    row_re = re.compile(rf"^(X+\d+)\s+(X+)\s+({_AMOUNT})\s*$")
    for line in block.group(1).splitlines():
        m = row_re.match(line.strip())
        if m:
            out.append({"account": m.group(1), "routing": m.group(2), "amount": _num(m.group(3))})
    return out


def _parse_tax_settings(text: str) -> dict[str, dict[str, str]]:
    """Exemptions/Allowances and Tax Override, each with Federal/State/Local values."""
    fed = re.search(r"Federal:[ \t]*([^\n]*?)[ \t]+Federal:[ \t]*([^\n]*)", text)
    state = re.search(r"State:[ \t]*([^\n]*?)[ \t]+State:[ \t]*([^\n]*)", text)
    local = re.search(r"Local:[ \t]*([^\n]*?)[ \t]+Local:[ \t]*([^\n]*)", text)
    return {
        "exemptions": {
            "federal": fed.group(1).strip() if fed else "",
            "state": state.group(1).strip() if state else "",
            "local": local.group(1).strip() if local else "",
        },
        "taxOverride": {
            "federal": fed.group(2).strip() if fed else "",
            "state": state.group(2).strip() if state else "",
            "local": local.group(2).strip() if local else "",
        },
    }


def _parse_important_notes(text: str) -> str:
    m = re.search(r"Important Notes\s*\n(.*?)$", text, re.DOTALL)
    return m.group(1).strip() if m else ""


def _parse_paystub_text(text: str) -> dict[str, Any]:
    period_start = _search(r"Period Starting:\s*([\d/]+)", text)
    period_end = _search(r"Period Ending:\s*([\d/]+)", text)
    pay_date = _search(r"Pay Date:\s*([\d/]+)", text)
    filing_status = _search(r"Taxable Filing Status:\s*([A-Za-z ]+)", text)
    ssn = _search(r"Social Security Number:\s*([\dX\-]+)", text)

    gross_match = re.search(rf"Gross Pay\s*\$?({_AMOUNT})\s*\$?({_AMOUNT})", text)
    gross_this = _num(gross_match.group(1)) if gross_match else None
    gross_ytd = _num(gross_match.group(2)) if gross_match else None

    net_match = re.search(rf"Net Pay\s+\$?({_AMOUNT})", text)
    net_pay = _num(net_match.group(1)) if net_match else None

    federal_taxable = _num(_search(rf"federal taxable wages this period are\s+\$?({_AMOUNT})", text, re.IGNORECASE))

    tax = _parse_tax_settings(text)

    return {
        "company": _parse_company(text),
        "employee": _parse_employee(text),
        "ssn": ssn,
        "periodStart": period_start,
        "periodEnd": period_end,
        "payDate": pay_date,
        "filingStatus": filing_status,
        "exemptions": tax["exemptions"],
        "taxOverride": tax["taxOverride"],
        "earnings": _parse_earnings(text),
        "grossPay": gross_this,
        "grossPayYtd": gross_ytd,
        "deductions": _parse_deductions(text),
        "netPay": net_pay,
        "federalTaxableWages": federal_taxable,
        "deposits": _parse_deposits(text),
        "depositsSummary": _parse_deposits_summary(text),
        "importantNotes": _parse_important_notes(text),
        "rawText": text,
    }


def parse_paystub(data: bytes) -> dict[str, Any]:
    return _parse_paystub_text(_extract_text(data))


def parse_paystubs(data: bytes) -> list[dict[str, Any]]:
    """Parse a multi-page PDF as one paystub per page."""
    return [_parse_paystub_text(text) for text in _extract_pages(data) if text.strip()]
