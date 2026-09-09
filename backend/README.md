# AINCURU × TAXLA — Backend

FastAPI + SQLAlchemy 2.0 + Alembic + ARQ + Redis + Playwright + Ollama.
Powers the MSME/Udyam registration automation pipeline.

---

## Prerequisites

| Component | Why | Install |
|---|---|---|
| Python ≥ 3.11 | Runtime | https://www.python.org/downloads/ |
| **Tesseract OCR (binary)** | Document OCR via `pytesseract` | **See below — not pip-installable** |
| Poppler | PDF → image for OCR (`pdf2image`) | `apt install poppler-utils` (Linux) / `brew install poppler` (macOS) / [Windows binary](https://github.com/oschwartz10612/poppler-windows) |
| Redis | ARQ job queue + pub/sub | `apt install redis-server` (Linux) / `brew install redis` (macOS) / [Windows port](https://github.com/microsoftarchive/redis) |
| PostgreSQL or SQLite | Primary store | SQLite ships with Python. Postgres optional — see `.env.example` |
| Ollama (optional) | Local LLM for field extraction | https://ollama.com/download |
| Playwright Chromium | Udyam portal automation | `playwright install chromium` (after `pip install playwright`) |

### Install Tesseract binary

`pytesseract` is a thin Python wrapper — **the Tesseract binary must be installed
on your OS first**. Without it, document uploads will fail with
`OcrUnavailableError` and the application transitions to `EXCEPTION` with
`error_code = "OCR_BINARY_MISSING"`.

| OS | Command |
|---|---|
| **Windows** | Download installer from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki). During install, **tick "Add to PATH"**. Restart your shell. |
| **macOS** | `brew install tesseract` |
| **Ubuntu / Debian** | `sudo apt install tesseract-ocr` |
| **Fedora / RHEL** | `sudo dnf install tesseract` |
| **Alpine** | `apk add tesseract-ocr` |

Verify after install:

```bash
tesseract --version
# Expected: tesseract x.xx.x ...
```

For Indian government IDs (PAN, Aadhaar), install the Hindi + English language
packs if you want better accuracy on bilingual cards:

- **Windows:** During the UB-Mannheim installer, tick `hin` (Hindi) and `eng` (English).
- **Linux:** `sudo apt install tesseract-ocr-hin tesseract-ocr-eng`

---

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
.venv\Scripts\activate             # Windows PowerShell

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Copy the env template and edit it
cp .env.example .env
# Edit .env: set JWT_SECRET (generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`)

# 4. Run database migrations
alembic upgrade head

# 5. (Optional) Seed initial admin/operator users
python scripts/seed_users.py

# 6. Start Redis (required for ARQ)
redis-server
```

---

## Running

Two processes need to be running concurrently — the API server and the ARQ
worker.

```bash
# Terminal 1: FastAPI / Uvicorn
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2: ARQ worker (consumes ocr_extraction_job + portal_automation_job)
arq worker.WorkerSettings

# Terminal 3 (optional): Ollama for local LLM extraction
ollama serve
# Then: ollama pull qwen2.5:3b
```

Visit http://127.0.0.1:8000/docs for the interactive OpenAPI explorer.

---

## Testing

```bash
# Full suite (uses NullPool under ENVIRONMENT=test — see tests/conftest.py)
pytest tests/ -q

# Specific suites
pytest tests/test_state_machine.py -v
pytest tests/test_ocr_pipeline.py -v          # skips if Tesseract missing
pytest tests/test_document_pipeline.py -v     # skips if Tesseract missing
pytest tests/test_playwright_automation.py -v # needs running Redis + mock portal
```

If Tesseract isn't installed, the OCR-related tests skip cleanly with a
message rather than failing — they will pass automatically once you install
the binary.

---

## Where to drop test documents

Uploaded documents land here by default (configurable via `.env`):

```
backend/storage/documents/
├── <application_id>/
│   ├── pan_<uuid>.png
│   ├── aadhaar_<uuid>.pdf
│   └── ...
```

To exercise the OCR pipeline manually:

```bash
# Drop a test PNG into storage
cp my_test_pan.png storage/documents/test_pan.png

# Hit the API (replace $TOKEN with a valid JWT)
curl -X POST http://127.0.0.1:8000/api/v1/applications/$APP_ID/documents \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@storage/documents/test_pan.png" \
     -F "type=PAN_CARD"

# Check ExtractedData rows in the database
psql -U taxla_user -d taxla_db -c \
     "SELECT field_name, field_value, confidence, bounding_box_json FROM extracted_data WHERE application_id = '$APP_ID';"
```

You should see real `field_value`, `confidence` (0-1), and populated
`bounding_box_json` (left/top/width/height) for each extracted field.

---

## Project layout

```
backend/
├── app/
│   ├── api/                  # FastAPI routers
│   ├── core/                 # config, database, security, state machine
│   ├── models/               # SQLAlchemy models
│   ├── schemas/              # Pydantic schemas
│   ├── services/             # ocr_service, ai_extractor, validation_engine, nic_service
│   └── repositories/         # Data-access layer
├── worker/
│   ├── ocr_worker.py         # ARQ job: OCR + LLM extraction
│   └── playwright_agent.py   # ARQ job: Udyam portal automation
├── tests/                    # pytest test suite
├── alembic/                  # Database migrations
├── storage/                  # Local document + certificate storage
└── requirements.txt
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `OcrUnavailableError` on upload | Tesseract binary missing | Install per table above; ensure `tesseract --version` works in the same shell as the worker |
| `pdf2image` `PDFInfoNotInstalledError` | Poppler not installed | Install Poppler (see Prerequisites table) |
| OCR returns no text on a real PAN | Image too low-DPI / wrong language pack | Scan at ≥ 300 DPI; install `tesseract-ocr-hin` for bilingual IDs |
| ARQ jobs never run | Redis not running | `redis-server` in another terminal |
| `RuntimeError: Event loop is closed` in tests | Engine pool spanning pytest-asyncio loops | Already mitigated in `tests/conftest.py` + `app/core/database.py` (NullPool when `ENVIRONMENT=test`) |
