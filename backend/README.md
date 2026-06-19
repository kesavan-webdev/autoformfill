# W-9 Parser Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

POST a PDF to `http://localhost:8000/parse` (multipart field name `file`).
