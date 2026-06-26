"use client";

import { useCallback, useRef, useState } from "react";

type W9Data = {
  name: string;
  businessName: string;
  classification: string;
  llcClassification: string;
  otherClassification: string;
  foreignPartners: boolean;
  exemptPayeeCode: string;
  fatcaCode: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  accountNumbers: string;
  requesterNameAddress: string;
  ssn: string;
  ein: string;
};

const EMPTY: W9Data = {
  name: "",
  businessName: "",
  classification: "",
  llcClassification: "",
  otherClassification: "",
  foreignPartners: false,
  exemptPayeeCode: "",
  fatcaCode: "",
  address: "",
  city: "",
  state: "",
  zip: "",
  accountNumbers: "",
  requesterNameAddress: "",
  ssn: "",
  ein: "",
};

const CLASSIFICATIONS = [
  { value: "", label: "—" },
  { value: "individual", label: "Individual / sole proprietor" },
  { value: "c_corp", label: "C Corporation" },
  { value: "s_corp", label: "S Corporation" },
  { value: "partnership", label: "Partnership" },
  { value: "trust_estate", label: "Trust / estate" },
  { value: "llc", label: "Limited liability company" },
  { value: "other", label: "Other" },
];

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Page() {
  const [form, setForm] = useState<W9Data>(EMPTY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const update = (k: keyof W9Data) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const target = e.target as HTMLInputElement;
    const value = target.type === "checkbox" ? target.checked : target.value;
    setForm((f) => ({ ...f, [k]: value as never }));
  };

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
      const res = await fetch(`${API}/parse`, { method: "POST", body: fd });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed (${res.status})`);
      }
      const data: W9Data = await res.json();
      setForm({ ...EMPTY, ...data });
      setStatus("Form populated from PDF — review and edit as needed.");
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

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("Submitted (see console).");
    console.log("W-9 submission", form);
  };

  return (
    <main>
      <h1>W-9 Autofill</h1>
      <p className="lead">Upload a completed IRS Form W-9 and we&apos;ll prefill the fields below.</p>

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
          <strong>{loading ? "Parsing…" : "Drop W-9 PDF here or click to choose"}</strong>
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

      <form className="card" onSubmit={submit}>
        <div className="field">
          <label>1. Name (as shown on your income tax return)</label>
          <input value={form.name} onChange={update("name")} />
        </div>
        <div className="field">
          <label>2. Business name / disregarded entity name (if different)</label>
          <input value={form.businessName} onChange={update("businessName")} />
        </div>
        <div className="field">
          <label>3. Federal tax classification</label>
          <select value={form.classification} onChange={update("classification")}>
            {CLASSIFICATIONS.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>
        <div className="row">
          <div className="field">
            <label>3a (LLC). Tax classification (C / S / P)</label>
            <input value={form.llcClassification} onChange={update("llcClassification")} maxLength={1} />
          </div>
          <div className="field">
            <label>3a. Other (description)</label>
            <input value={form.otherClassification} onChange={update("otherClassification")} />
          </div>
        </div>
        <div className="field">
          <label>
            <input
              type="checkbox"
              checked={form.foreignPartners}
              onChange={update("foreignPartners")}
              style={{ width: "auto", marginRight: 8 }}
            />
            3b. Has foreign partners, owners, or beneficiaries
          </label>
        </div>
        <div className="row">
          <div className="field">
            <label>4a. Exempt payee code</label>
            <input value={form.exemptPayeeCode} onChange={update("exemptPayeeCode")} />
          </div>
          <div className="field">
            <label>4b. FATCA reporting code</label>
            <input value={form.fatcaCode} onChange={update("fatcaCode")} />
          </div>
        </div>
        <div className="field">
          <label>5. Address (number, street, apt/suite)</label>
          <input value={form.address} onChange={update("address")} />
        </div>
        <div className="row-3">
          <div className="field">
            <label>6. City</label>
            <input value={form.city} onChange={update("city")} />
          </div>
          <div className="field">
            <label>State</label>
            <input value={form.state} onChange={update("state")} maxLength={2} />
          </div>
          <div className="field">
            <label>ZIP</label>
            <input value={form.zip} onChange={update("zip")} />
          </div>
        </div>
        <div className="field">
          <label>7. Account numbers (optional)</label>
          <input value={form.accountNumbers} onChange={update("accountNumbers")} />
        </div>
        <div className="field">
          <label>Requester&apos;s name and address (optional)</label>
          <input value={form.requesterNameAddress} onChange={update("requesterNameAddress")} />
        </div>
        <div className="row">
          <div className="field">
            <label>Social security number</label>
            <input value={form.ssn} onChange={update("ssn")} placeholder="XXX-XX-XXXX" />
          </div>
          <div className="field">
            <label>Employer identification number</label>
            <input value={form.ein} onChange={update("ein")} placeholder="XX-XXXXXXX" />
          </div>
        </div>

        <div className="actions">
          <button type="submit">Submit</button>
          <button type="button" className="secondary" onClick={() => setForm(EMPTY)}>
            Clear
          </button>
        </div>
      </form>
    </main>
  );
}
