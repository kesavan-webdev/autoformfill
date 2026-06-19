# W-9 PDF Parse & Autofill

Two services:

- [backend/](backend/) — FastAPI + pypdf. Extracts AcroForm fields from a W-9 PDF.
- [frontend/](frontend/) — Next.js (App Router). Upload UI and autofill form.

## Run

```bash
# 1) backend
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 2) frontend (in a second terminal)
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Open http://localhost:3000 and drop `sample_w9.pdf` onto the dropzone.

## How parsing works

The IRS W-9 ships with AcroForm fields (`f1_1`…`f1_13`, classification checkbox group `c1_1`).
[backend/main.py](backend/main.py) reads them with `pypdf`, maps each field to a friendly key,
splits the combined "City, State ZIP" string, and assembles SSN/EIN from their digit segments.
The frontend POSTs the file to `/parse` and spreads the JSON response into form state.
