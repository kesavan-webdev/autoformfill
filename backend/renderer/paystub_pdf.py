"""ReportLab renderer for ADP-style paystubs.

Coordinates are tuned to match the ADP "Earnings Statement" reference layout.
All positions are in points (1/72 inch); Letter page is 612 x 792.
"""
from __future__ import annotations

import io
import os
from typing import Any

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


PAGE_W, PAGE_H = letter  # 612 x 792
ADP_RED = HexColor("#D71920")
_LOGO_DIR = os.path.dirname(__file__)
LOGO_CANDIDATES = [
    os.path.join(_LOGO_DIR, "adp_logo.png"),
    os.path.join(_LOGO_DIR, "adp_logo.jpg"),
    os.path.join(_LOGO_DIR, "adp_logo.jpeg"),
]


def _fmt(n: Any) -> str:
    if n is None or n == "":
        return ""
    try:
        return f"{float(n):,.2f}"
    except (TypeError, ValueError):
        return str(n)


def _fmt_dollar(n: Any) -> str:
    v = _fmt(n)
    return f"${v}" if v else ""


def _s(v: Any) -> str:
    return "" if v is None else str(v)


def _draw_adp_badge(c: canvas.Canvas, cx: float, cy: float) -> None:
    """Draw the ADP logo. Uses adp_logo.png if present, else a red rounded-rect fallback."""
    logo = next((p for p in LOGO_CANDIDATES if os.path.exists(p)), None)
    if logo:
        w, h = 60, 22
        c.drawImage(logo, cx - w / 2, cy - h / 2, width=w, height=h, mask="auto", preserveAspectRatio=True)
        return
    w, h = 40, 18
    x, y = cx - w / 2, cy - h / 2
    c.saveState()
    c.setFillColor(ADP_RED)
    c.roundRect(x, y, w, h, 3, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(cx, y + 4, "ADP")
    c.restoreState()
    c.setFillColor(black)
    c.setFont("Helvetica", 5)
    c.drawString(x + w + 1, y + h - 3, "®")


def _draw_header(c: canvas.Canvas, data: dict[str, Any]) -> None:
    company = data.get("company", {}) or {}

    # Left header grid — indented from left edge.
    gx = 130.0
    gy = 748.0
    labels = ["Company Code", "Loc/Dept", "Number", "Page"]
    values = [
        _s(company.get("code")),
        _s(company.get("locDept")),
        _s(company.get("fileNumber")),
        _s(company.get("page") or "1 of 1"),
    ]
    col_widths = [96, 42, 46, 40]
    c.setFont("Helvetica-Bold", 8)
    x = gx
    for label, w in zip(labels, col_widths):
        c.drawString(x, gy, label)
        x += w
    x = gx
    for value, w in zip(values, col_widths):
        c.drawString(x, gy - 10, value)
        x += w

    # Company name/address block below the grid.
    cy = gy - 22
    c.setFont("Helvetica", 8)
    c.drawString(gx + 20, cy, _s(company.get("name")))
    for line in company.get("addressLines", []) or []:
        cy -= 10
        c.drawString(gx + 20, cy, _s(line))
    if company.get("cityStateZip"):
        cy -= 10
        c.drawString(gx + 20, cy, _s(company.get("cityStateZip")))

    # Center title.
    c.setFont("Helvetica-Bold", 15)
    c.drawString(360, 748, "Earnings Statement")

    # ADP badge (top right).
    _draw_adp_badge(c, 560, 748)

    # Period dates under title.
    c.setFont("Helvetica", 8)
    lx, vx = 360, 428
    y = 720
    for label, val in [
        ("Period Starting:", _s(data.get("periodStart"))),
        ("Period Ending:", _s(data.get("periodEnd"))),
        ("Pay Date:", _s(data.get("payDate"))),
    ]:
        c.drawString(lx, y, label)
        c.drawString(vx, y, val)
        y -= 10


def _draw_tax_and_employee(c: canvas.Canvas, data: dict[str, Any]) -> None:
    # Tax block (left)
    lx = 90.0
    ly = 622.0
    c.setFont("Helvetica", 8)
    c.drawString(lx, ly, f"Taxable Filing Status: {_s(data.get('filingStatus'))}")
    ly -= 11
    c.drawString(lx, ly, "Exemptions/Allowances:")
    c.drawString(lx + 152, ly, "Tax Override:")
    ex = data.get("exemptions", {}) or {}
    ov = data.get("taxOverride", {}) or {}
    for label, ek in [("Federal", "federal"), ("State", "state"), ("Local", "local")]:
        ly -= 10
        c.drawString(lx + 10, ly, f"{label}:")
        c.drawString(lx + 52, ly, _s(ex.get(ek)))
        c.drawString(lx + 162, ly, f"{label}:")
        c.drawString(lx + 204, ly, _s(ov.get(ek)))
    ly -= 12
    c.drawString(lx, ly, f"Social Security Number:{_s(data.get('ssn'))}")

    # Employee block (right, bold).
    emp = data.get("employee", {}) or {}
    rx = 358.0
    ry = 622.0
    c.setFont("Helvetica-Bold", 10)
    c.drawString(rx, ry, _s(emp.get("name")))
    for line in [emp.get("address1"), emp.get("address2"), emp.get("cityStateZip")]:
        if line:
            ry -= 12
            c.drawString(rx, ry, _s(line))


def _draw_table(
    c: canvas.Canvas,
    x: float,
    y: float,
    col_x: list[float],
    headers: list[str],
    rows: list[list[str]],
    aligns: list[str],
    right_edge: float,
) -> float:
    """Draws a header row with underline, then data rows. Returns y after the table."""
    c.setFont("Helvetica-Bold", 8)
    for i, h in enumerate(headers):
        if aligns[i] == "right":
            c.drawRightString(col_x[i], y, h)
        else:
            c.drawString(col_x[i], y, h)
    y -= 2
    c.line(x, y, right_edge, y)
    y -= 11
    c.setFont("Helvetica", 8)
    for row in rows:
        for i, val in enumerate(row):
            if aligns[i] == "right":
                c.drawRightString(col_x[i], y, val)
            else:
                c.drawString(col_x[i], y, val)
        y -= 11
    return y


def _draw_body(c: canvas.Canvas, data: dict[str, Any]) -> None:
    # ---------- LEFT column: Earnings, Gross Pay, Deductions, Net Pay ----------
    lx = 50.0
    left_right = 380.0
    # Column x positions for Earnings table (right edges for numeric cols).
    e_cols = [lx, 200.0, 260.0, 320.0, 380.0]
    ly = 500.0
    earn_rows = []
    for e in data.get("earnings", []) or []:
        earn_rows.append([
            _s(e.get("label")),
            _fmt(e.get("rate")),
            _fmt(e.get("hours")),
            _fmt(e.get("thisPeriod")),
            _fmt(e.get("ytd")),
        ])
    ly = _draw_table(
        c, lx, ly, e_cols,
        ["Earnings", "rate", "hours/units", "this period", "year to date"],
        earn_rows,
        ["left", "right", "right", "right", "right"],
        right_edge=left_right,
    )

    ly -= 6
    gross_left = lx + 40
    gross_right = e_cols[4]
    c.line(gross_left, ly + 9, gross_right, ly + 9)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(gross_left, ly, "Gross Pay")
    c.drawRightString(e_cols[3], ly, _fmt_dollar(data.get("grossPay")))
    c.drawRightString(e_cols[4], ly, _fmt_dollar(data.get("grossPayYtd")))
    ly -= 3
    c.line(gross_left, ly, gross_right, ly)
    ly -= 22

    # Deductions table (only 3 columns).
    d_cols = [lx + 40, 300.0, 380.0]
    ded_rows = []
    for d in data.get("deductions", []) or []:
        ded_rows.append([
            _s(d.get("label")),
            _fmt(d.get("thisPeriod")),
            _fmt(d.get("ytd")),
        ])
    ly = _draw_table(
        c, lx, ly, d_cols,
        ["Statutory Deductions", "this period", "year to date"],
        ded_rows,
        ["left", "right", "right"],
        right_edge=left_right,
    )

    ly -= 6
    net_left = lx + 40
    net_right = e_cols[3]
    c.line(net_left, ly + 9, net_right, ly + 9)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(net_left, ly, "Net Pay")
    c.drawRightString(net_right, ly, _fmt_dollar(data.get("netPay")))
    ly -= 3
    c.line(net_left, ly, net_right, ly)

    # ---------- RIGHT column: Deposits + Important Notes ----------
    # Right column sits to the right of the earnings table (which ends at 380).
    rx = 570.0   # right edge
    hx = 395.0   # left edge of right column
    ry = 462.0   # roughly level with the Statutory Deductions header on the left

    c.setFont("Helvetica-Bold", 8)
    c.drawString(hx, ry, "Deposits")
    ry -= 12
    dep_x = [hx, hx + 75.0, rx]
    dep_rows = []
    for d in data.get("depositsSummary", []) or []:
        dep_rows.append([
            _s(d.get("account")),
            _s(d.get("routing")),
            _fmt(d.get("amount")),
        ])
    ry = _draw_table(
        c, hx, ry, dep_x,
        ["account number", "transit/ABA", "amount"],
        dep_rows,
        ["left", "left", "right"],
        right_edge=rx,
    )

    ry -= 10
    c.setFont("Helvetica-Bold", 8)
    c.drawString(hx, ry, "Important Notes")
    ry -= 2
    c.line(hx, ry, rx, ry)
    ry -= 11
    c.setFont("Helvetica", 8)
    for line in _s(data.get("importantNotes")).splitlines():
        c.drawString(hx, ry, line)
        ry -= 10


def _draw_federal_wages(c: canvas.Canvas, data: dict[str, Any]) -> None:
    fed = data.get("federalTaxableWages")
    if fed is None:
        return
    c.setFont("Helvetica", 8)
    c.drawRightString(555.0, 172.0, f"Your federal taxable wages this period are  ${_fmt(fed)}")


def _draw_tearoff(c: canvas.Canvas, data: dict[str, Any]) -> None:
    company = data.get("company", {}) or {}

    # Watermark first (behind everything). Position between the middle content
    # and the tear-off deposit row so it doesn't obscure key text.
    c.saveState()
    c.setFillGray(0.78)
    c.setFont("Helvetica-Bold", 30)
    c.translate(PAGE_W / 2, 90)
    c.rotate(9)
    c.drawCentredString(0, 0, "THIS IS NOT A CHECK")
    c.restoreState()

    # Company block (left).
    lx = 90.0
    ly = 140.0
    c.setFont("Helvetica", 8)
    c.drawString(lx, ly, _s(company.get("name")))
    for line in company.get("addressLines", []) or []:
        ly -= 10
        c.drawString(lx, ly, _s(line))
    if company.get("cityStateZip"):
        ly -= 10
        c.drawString(lx, ly, _s(company.get("cityStateZip")))

    # Pay Date (center).
    c.setFont("Helvetica-Bold", 9)
    c.drawString(300, 130, "Pay Date:")
    c.setFont("Helvetica", 9)
    c.drawString(370, 130, _s(data.get("payDate")))

    # "Deposited to the account" header + rows.
    ty = 60.0
    c.setFont("Helvetica-Bold", 8)
    c.drawString(50, ty, "Deposited to the account")
    c.drawString(310, ty, "account number")
    c.drawString(430, ty, "transit/ABA")
    c.drawRightString(560, ty, "amount")
    c.line(50, ty - 2, 560, ty - 2)
    ty -= 12
    c.setFont("Helvetica", 8)
    for d in data.get("deposits", []) or []:
        c.drawString(50, ty, f"{_s(d.get('accountType'))} {_s(d.get('method'))}".strip())
        c.drawString(310, ty, _s(d.get("account")))
        c.drawString(430, ty, _s(d.get("routing")))
        c.drawRightString(560, ty, _fmt(d.get("amount")))
        ty -= 11


def render_paystub_pdf(data: dict[str, Any]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    _draw_header(c, data)
    _draw_tax_and_employee(c, data)
    _draw_body(c, data)
    _draw_federal_wages(c, data)
    _draw_tearoff(c, data)
    c.showPage()
    c.save()
    return buf.getvalue()
