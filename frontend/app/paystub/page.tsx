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

type PaystubData = {
  company: { code: string; name: string; address: string };
  employee: { name: string; address1: string; address2: string; cityStateZip: string };
  periodStart: string;
  periodEnd: string;
  payDate: string;
  filingStatus: string;
  earnings: EarningRow[];
  grossPay: number | null;
  grossPayYtd: number | null;
  deductions: DeductionRow[];
  netPay: number | null;
  federalTaxableWages: number | null;
  deposit: {
    accountType: string;
    method: string;
    account: string;
    routing: string;
    amount: number | null;
  };
};

const EMPTY: PaystubData = {
  company: { code: "", name: "", address: "" },
  employee: { name: "", address1: "", address2: "", cityStateZip: "" },
  periodStart: "",
  periodEnd: "",
  payDate: "",
  filingStatus: "",
  earnings: [],
  grossPay: null,
  grossPayYtd: null,
  deductions: [],
  netPay: null,
  federalTaxableWages: null,
  deposit: { accountType: "", method: "", account: "", routing: "", amount: null },
};

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const fmt = (n: number | null) =>
  n == null ? "" : n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function PaystubPage() {
  const [data, setData] = useState<PaystubData>(EMPTY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

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
      const res = await fetch(`${API}/parse/paystub`, { method: "POST", body: fd });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed (${res.status})`);
      }
      const parsed: PaystubData = await res.json();
      setData({ ...EMPTY, ...parsed });
      setStatus("Paystub parsed — review fields below.");
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

  const setField = <K extends keyof PaystubData>(key: K, value: PaystubData[K]) =>
    setData((d) => ({ ...d, [key]: value }));

  const setCompany = (k: keyof PaystubData["company"]) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setData((d) => ({ ...d, company: { ...d.company, [k]: e.target.value } }));

  const setEmployee = (k: keyof PaystubData["employee"]) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setData((d) => ({ ...d, employee: { ...d.employee, [k]: e.target.value } }));

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
        <div className="field">
          <label>Address</label>
          <input value={data.company.address} onChange={setCompany("address")} />
        </div>

        <div className="subhead">Employee</div>
        <div className="field">
          <label>Name</label>
          <input value={data.employee.name} onChange={setEmployee("name")} />
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
        {data.earnings.length === 0 ? (
          <p style={{ color: "#6b7280", fontSize: 14 }}>No earnings lines parsed.</p>
        ) : (
          <table className="lines">
            <thead>
              <tr>
                <th>Type</th>
                <th>Rate</th>
                <th>Hours</th>
                <th>This Period</th>
                <th>YTD</th>
              </tr>
            </thead>
            <tbody>
              {data.earnings.map((row, i) => (
                <tr key={i}>
                  <td>{row.label}</td>
                  <td className="num">{fmt(row.rate)}</td>
                  <td className="num">{fmt(row.hours)}</td>
                  <td className="num">{fmt(row.thisPeriod)}</td>
                  <td className="num">{fmt(row.ytd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="row" style={{ marginTop: 12 }}>
          <div className="field">
            <label>Gross Pay (this period)</label>
            <input value={fmt(data.grossPay)} onChange={(e) => setField("grossPay", Number(e.target.value) || null)} />
          </div>
          <div className="field">
            <label>Gross Pay (YTD)</label>
            <input value={fmt(data.grossPayYtd)} onChange={(e) => setField("grossPayYtd", Number(e.target.value) || null)} />
          </div>
        </div>

        <div className="subhead">Statutory Deductions</div>
        {data.deductions.length === 0 ? (
          <p style={{ color: "#6b7280", fontSize: 14 }}>No deductions parsed.</p>
        ) : (
          <table className="lines">
            <thead>
              <tr>
                <th>Label</th>
                <th>This Period</th>
                <th>YTD</th>
              </tr>
            </thead>
            <tbody>
              {data.deductions.map((row, i) => (
                <tr key={i}>
                  <td>{row.label}</td>
                  <td className="num">{fmt(row.thisPeriod)}</td>
                  <td className="num">{fmt(row.ytd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="row" style={{ marginTop: 12 }}>
          <div className="field">
            <label>Net Pay</label>
            <input value={fmt(data.netPay)} onChange={(e) => setField("netPay", Number(e.target.value) || null)} />
          </div>
          <div className="field">
            <label>Federal Taxable Wages (this period)</label>
            <input
              value={fmt(data.federalTaxableWages)}
              onChange={(e) => setField("federalTaxableWages", Number(e.target.value) || null)}
            />
          </div>
        </div>

        <div className="subhead">Direct Deposit</div>
        <div className="row-3">
          <div className="field">
            <label>Account Type</label>
            <input value={data.deposit.accountType} onChange={(e) => setData((d) => ({ ...d, deposit: { ...d.deposit, accountType: e.target.value } }))} />
          </div>
          <div className="field">
            <label>Account</label>
            <input value={data.deposit.account} onChange={(e) => setData((d) => ({ ...d, deposit: { ...d.deposit, account: e.target.value } }))} />
          </div>
          <div className="field">
            <label>Amount</label>
            <input value={fmt(data.deposit.amount)} onChange={(e) => setData((d) => ({ ...d, deposit: { ...d.deposit, amount: Number(e.target.value) || null } }))} />
          </div>
        </div>

        <div className="actions">
          <button type="submit">Submit</button>
          <button type="button" className="secondary" onClick={() => setData(EMPTY)}>Clear</button>
        </div>
      </form>
    </main>
  );
}
