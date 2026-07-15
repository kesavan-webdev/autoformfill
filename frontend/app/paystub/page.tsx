"use client";

import { useCallback, useRef, useState } from "react";

type EarningRow = {
  label: string;
  rate: number | null;
  hours: number | null;
  thisPeriod: number | null;
  ytd: number | null;
};

type DeductionRow = {
  label: string;
  thisPeriod: number | null;
  ytd: number | null;
};

type DepositRow = {
  accountType: string;
  method: string;
  account: string;
  routing: string;
  amount: number | null;
};

type DepositSummaryRow = { account: string; routing: string; amount: number | null };

type PaystubData = {
  company: {
    code: string;
    locDept: string;
    fileNumber: string;
    page: string;
    name: string;
    addressLines: string[];
    cityStateZip: string;
  };
  employee: { name: string; address1: string; address2: string; cityStateZip: string };
  ssn: string;
  periodStart: string;
  periodEnd: string;
  payDate: string;
  filingStatus: string;
  exemptions: { federal: string; state: string; local: string };
  taxOverride: { federal: string; state: string; local: string };
  earnings: EarningRow[];
  grossPay: number | null;
  grossPayYtd: number | null;
  deductions: DeductionRow[];
  netPay: number | null;
  federalTaxableWages: number | null;
  deposits: DepositRow[];
  depositsSummary: DepositSummaryRow[];
  importantNotes: string;
  rawText?: string;
};

const EMPTY: PaystubData = {
  company: { code: "", locDept: "", fileNumber: "", page: "", name: "", addressLines: [], cityStateZip: "" },
  employee: { name: "", address1: "", address2: "", cityStateZip: "" },
  ssn: "",
  periodStart: "",
  periodEnd: "",
  payDate: "",
  filingStatus: "",
  exemptions: { federal: "", state: "", local: "" },
  taxOverride: { federal: "", state: "", local: "" },
  earnings: [],
  grossPay: null,
  grossPayYtd: null,
  deductions: [],
  netPay: null,
  federalTaxableWages: null,
  deposits: [],
  depositsSummary: [],
  importantNotes: "",
};

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const fmt = (n: number | null) =>
  n == null ? "" : n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function PaystubPage() {
  const [stubs, setStubs] = useState<PaystubData[]>([]);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const data: PaystubData = stubs[index] ?? EMPTY;

  const upload = useCallback(async (file: File) => {
    setError("");
    setStatus("");
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Please upload a PDF file.");
      return;
    }
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${API}/parse/paystubs`, { method: "POST", body: fd });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed (${res.status})`);
      }
      const json = await res.json();
      const parsed: PaystubData[] = (json.paystubs || []).map((p: PaystubData) => ({ ...EMPTY, ...p }));
      if (parsed.length === 0) {
        setError("No paystubs found in PDF.");
        return;
      }
      setStubs(parsed);
      setIndex(0);
      setStatus(`Parsed ${parsed.length} paystub${parsed.length === 1 ? "" : "s"} — review below.`);
    } catch (e: any) {
      setError(e.message || "Upload failed");
    } finally {
      setLoading(false);
    }
  }, []);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) upload(file);
  };

  const setData = (updater: (d: PaystubData) => PaystubData) =>
    setStubs((list) => list.map((s, i) => (i === index ? updater(s) : s)));

  const downloadPdf = async () => {
    setError("");
    try {
      const res = await fetch(`${API}/render/paystub`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Render failed (${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `paystub-${data.payDate || index + 1}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e.message || "Download failed");
    }
  };

  const setField = <K extends keyof PaystubData>(key: K, value: PaystubData[K]) =>
    setData((d) => ({ ...d, [key]: value }));

  const setCompany = (k: keyof PaystubData["company"]) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setData((d) => ({ ...d, company: { ...d.company, [k]: e.target.value } }));

  const setEmployee = (k: keyof PaystubData["employee"]) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setData((d) => ({ ...d, employee: { ...d.employee, [k]: e.target.value } }));

  const parseNum = (v: string): number | null => {
    const cleaned = v.replace(/[,$\s]/g, "");
    if (cleaned === "" || cleaned === "-") return null;
    const n = Number(cleaned);
    return Number.isFinite(n) ? n : null;
  };

  const updateEarning = (i: number, k: keyof EarningRow, v: string) =>
    setData((d) => ({
      ...d,
      earnings: d.earnings.map((r, j) =>
        j === i ? { ...r, [k]: k === "label" ? v : parseNum(v) } : r
      ),
    }));

  const updateDeduction = (i: number, k: keyof DeductionRow, v: string) =>
    setData((d) => ({
      ...d,
      deductions: d.deductions.map((r, j) =>
        j === i ? { ...r, [k]: k === "label" ? v : parseNum(v) } : r
      ),
    }));

  const updateDeposit = (i: number, k: keyof DepositRow, v: string) =>
    setData((d) => ({
      ...d,
      deposits: d.deposits.map((r, j) =>
        j === i ? { ...r, [k]: k === "amount" ? parseNum(v) : v } : r
      ),
    }));

  const addEarning = () =>
    setData((d) => ({ ...d, earnings: [...d.earnings, { label: "", rate: null, hours: null, thisPeriod: null, ytd: null }] }));
  const removeEarning = (i: number) =>
    setData((d) => ({ ...d, earnings: d.earnings.filter((_, j) => j !== i) }));

  const addDeduction = () =>
    setData((d) => ({ ...d, deductions: [...d.deductions, { label: "", thisPeriod: null, ytd: null }] }));
  const removeDeduction = (i: number) =>
    setData((d) => ({ ...d, deductions: d.deductions.filter((_, j) => j !== i) }));

  const addDeposit = () =>
    setData((d) => ({ ...d, deposits: [...d.deposits, { accountType: "", method: "", account: "", routing: "", amount: null }] }));
  const removeDeposit = (i: number) =>
    setData((d) => ({ ...d, deposits: d.deposits.filter((_, j) => j !== i) }));

  return (
    <main>
      <h1>Paystub Parser</h1>
      <p className="lead">Upload an ADP-style earnings statement PDF to extract its fields.</p>

      <div className="card">
        <div
          className={`dropzone${dragging ? " dragging" : ""}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <strong>{loading ? "Parsing…" : "Drop paystub PDF here or click to choose"}</strong>
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) upload(f);
            }}
          />
        </div>
        {error && <div className="error">{error}</div>}
        {status && <div className="status">{status}</div>}
      </div>

      {stubs.length > 1 && (
        <div className="card" style={{ display: "flex", alignItems: "center", gap: 12, justifyContent: "space-between" }}>
          <button type="button" className="secondary" disabled={index === 0} onClick={() => setIndex((i) => Math.max(0, i - 1))}>
            ← Previous
          </button>
          <strong>Paystub {index + 1} of {stubs.length}</strong>
          <button type="button" disabled={index >= stubs.length - 1} onClick={() => setIndex((i) => Math.min(stubs.length - 1, i + 1))}>
            Next →
          </button>
        </div>
      )}

      <form className="card" onSubmit={(e) => { e.preventDefault(); console.log("paystub", data); setStatus("Submitted (see console)."); }}>
        <div className="subhead">Pay period</div>
        <div className="row-3">
          <div className="field">
            <label>Period Start</label>
            <input value={data.periodStart} onChange={(e) => setField("periodStart", e.target.value)} />
          </div>
          <div className="field">
            <label>Period End</label>
            <input value={data.periodEnd} onChange={(e) => setField("periodEnd", e.target.value)} />
          </div>
          <div className="field">
            <label>Pay Date</label>
            <input value={data.payDate} onChange={(e) => setField("payDate", e.target.value)} />
          </div>
        </div>
        <div className="field">
          <label>Filing Status</label>
          <input value={data.filingStatus} onChange={(e) => setField("filingStatus", e.target.value)} />
        </div>

        <div className="subhead">Employer</div>
        <div className="row">
          <div className="field">
            <label>Company Name</label>
            <input value={data.company.name} onChange={setCompany("name")} />
          </div>
          <div className="field">
            <label>Company Code</label>
            <input value={data.company.code} onChange={setCompany("code")} />
          </div>
        </div>
        <div className="row">
          <div className="field">
            <label>Loc/Dept</label>
            <input value={data.company.locDept} onChange={setCompany("locDept")} />
          </div>
          <div className="field">
            <label>Number</label>
            <input value={data.company.fileNumber} onChange={setCompany("fileNumber")} />
          </div>
        </div>
        <div className="field">
          <label>Address (one line per row)</label>
          <textarea
            rows={2}
            value={(data.company.addressLines || []).join("\n")}
            onChange={(e) => setData((d) => ({ ...d, company: { ...d.company, addressLines: e.target.value.split("\n") } }))}
          />
        </div>
        <div className="row">
          <div className="field">
            <label>City, State ZIP</label>
            <input value={data.company.cityStateZip} onChange={setCompany("cityStateZip")} />
          </div>
          <div className="field">
            <label>Page</label>
            <input value={data.company.page} onChange={setCompany("page")} />
          </div>
        </div>

        <div className="subhead">Tax</div>
        <div className="row-3">
          <div className="field">
            <label>Exemptions — Federal</label>
            <input value={data.exemptions.federal} onChange={(e) => setData((d) => ({ ...d, exemptions: { ...d.exemptions, federal: e.target.value } }))} />
          </div>
          <div className="field">
            <label>Exemptions — State</label>
            <input value={data.exemptions.state} onChange={(e) => setData((d) => ({ ...d, exemptions: { ...d.exemptions, state: e.target.value } }))} />
          </div>
          <div className="field">
            <label>Exemptions — Local</label>
            <input value={data.exemptions.local} onChange={(e) => setData((d) => ({ ...d, exemptions: { ...d.exemptions, local: e.target.value } }))} />
          </div>
        </div>
        <div className="row-3">
          <div className="field">
            <label>Tax Override — Federal</label>
            <input value={data.taxOverride.federal} onChange={(e) => setData((d) => ({ ...d, taxOverride: { ...d.taxOverride, federal: e.target.value } }))} />
          </div>
          <div className="field">
            <label>Tax Override — State</label>
            <input value={data.taxOverride.state} onChange={(e) => setData((d) => ({ ...d, taxOverride: { ...d.taxOverride, state: e.target.value } }))} />
          </div>
          <div className="field">
            <label>Tax Override — Local</label>
            <input value={data.taxOverride.local} onChange={(e) => setData((d) => ({ ...d, taxOverride: { ...d.taxOverride, local: e.target.value } }))} />
          </div>
        </div>

        <div className="subhead">Employee</div>
        <div className="row">
          <div className="field">
            <label>Name</label>
            <input value={data.employee.name} onChange={setEmployee("name")} />
          </div>
          <div className="field">
            <label>SSN</label>
            <input value={data.ssn} onChange={(e) => setField("ssn", e.target.value)} />
          </div>
        </div>
        <div className="row">
          <div className="field">
            <label>Address line 1</label>
            <input value={data.employee.address1} onChange={setEmployee("address1")} />
          </div>
          <div className="field">
            <label>Address line 2</label>
            <input value={data.employee.address2} onChange={setEmployee("address2")} />
          </div>
        </div>
        <div className="field">
          <label>City, State ZIP</label>
          <input value={data.employee.cityStateZip} onChange={setEmployee("cityStateZip")} />
        </div>

        <div className="subhead">Earnings</div>
        <table className="lines">
          <thead>
            <tr>
              <th>Type</th>
              <th>Rate</th>
              <th>Hours</th>
              <th>This Period</th>
              <th>YTD</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.earnings.map((row, i) => (
              <tr key={i}>
                <td><input value={row.label} onChange={(e) => updateEarning(i, "label", e.target.value)} /></td>
                <td><input className="num" value={row.rate ?? ""} onChange={(e) => updateEarning(i, "rate", e.target.value)} /></td>
                <td><input className="num" value={row.hours ?? ""} onChange={(e) => updateEarning(i, "hours", e.target.value)} /></td>
                <td><input className="num" value={row.thisPeriod ?? ""} onChange={(e) => updateEarning(i, "thisPeriod", e.target.value)} /></td>
                <td><input className="num" value={row.ytd ?? ""} onChange={(e) => updateEarning(i, "ytd", e.target.value)} /></td>
                <td><button type="button" className="secondary" onClick={() => removeEarning(i)}>×</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <button type="button" className="secondary" onClick={addEarning} style={{ marginTop: 6 }}>+ Add earning</button>

        <div className="row" style={{ marginTop: 12 }}>
          <div className="field">
            <label>Gross Pay (this period)</label>
            <input value={data.grossPay ?? ""} onChange={(e) => setField("grossPay", parseNum(e.target.value))} />
          </div>
          <div className="field">
            <label>Gross Pay (YTD)</label>
            <input value={data.grossPayYtd ?? ""} onChange={(e) => setField("grossPayYtd", parseNum(e.target.value))} />
          </div>
        </div>

        <div className="subhead">Statutory Deductions</div>
        <table className="lines">
          <thead>
            <tr>
              <th>Label</th>
              <th>This Period</th>
              <th>YTD</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.deductions.map((row, i) => (
              <tr key={i}>
                <td><input value={row.label} onChange={(e) => updateDeduction(i, "label", e.target.value)} /></td>
                <td><input className="num" value={row.thisPeriod ?? ""} onChange={(e) => updateDeduction(i, "thisPeriod", e.target.value)} /></td>
                <td><input className="num" value={row.ytd ?? ""} onChange={(e) => updateDeduction(i, "ytd", e.target.value)} /></td>
                <td><button type="button" className="secondary" onClick={() => removeDeduction(i)}>×</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <button type="button" className="secondary" onClick={addDeduction} style={{ marginTop: 6 }}>+ Add deduction</button>

        <div className="row" style={{ marginTop: 12 }}>
          <div className="field">
            <label>Net Pay</label>
            <input value={data.netPay ?? ""} onChange={(e) => setField("netPay", parseNum(e.target.value))} />
          </div>
          <div className="field">
            <label>Federal Taxable Wages (this period)</label>
            <input
              value={data.federalTaxableWages ?? ""}
              onChange={(e) => setField("federalTaxableWages", parseNum(e.target.value))}
            />
          </div>
        </div>

        <div className="subhead">Direct Deposit</div>
        <table className="lines">
          <thead>
            <tr>
              <th>Account Type</th>
              <th>Method</th>
              <th>Account</th>
              <th>Transit/ABA</th>
              <th>Amount</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.deposits.map((row, i) => (
              <tr key={i}>
                <td><input value={row.accountType} onChange={(e) => updateDeposit(i, "accountType", e.target.value)} /></td>
                <td><input value={row.method} onChange={(e) => updateDeposit(i, "method", e.target.value)} /></td>
                <td><input value={row.account} onChange={(e) => updateDeposit(i, "account", e.target.value)} /></td>
                <td><input value={row.routing} onChange={(e) => updateDeposit(i, "routing", e.target.value)} /></td>
                <td><input className="num" value={row.amount ?? ""} onChange={(e) => updateDeposit(i, "amount", e.target.value)} /></td>
                <td><button type="button" className="secondary" onClick={() => removeDeposit(i)}>×</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <button type="button" className="secondary" onClick={addDeposit} style={{ marginTop: 6 }}>+ Add deposit</button>

        <div className="subhead">Important Notes</div>
        <div className="field">
          <textarea rows={2} value={data.importantNotes} onChange={(e) => setField("importantNotes", e.target.value)} />
        </div>

        <div className="actions">
          <button type="submit">Submit</button>
          <button type="button" onClick={downloadPdf} disabled={loading || stubs.length === 0}>Download PDF</button>
          <button type="button" className="secondary" onClick={() => { setStubs([]); setIndex(0); setStatus(""); }}>Clear</button>
        </div>
      </form>
    </main>
  );
}
