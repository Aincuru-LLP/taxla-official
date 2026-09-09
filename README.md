# 🏛️ Taxla MSME (Udyam) AI Registration Intake Engine

[![Next.js 14](https://img.shields.io/badge/Next.js-14.2-black?logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python)](https://www.python.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-v3.4-38BDF8?logo=tailwindcss)](https://tailwindcss.com/)
[![Gemini 3.6 Flash](https://img.shields.io/badge/Google_Gemini-3.6_Flash-8E44AD?logo=google)](https://ai.google.dev/)

An enterprise-grade, AI-powered intake and document automation platform for **Government of India MSME (Udyam) Registrations**. Built for tax professionals, legal consultants, and enterprise advisors to streamline client requirement gathering, document OCR extraction, template generation, and case submission under official 2026 government threshold rules.

---

## ✨ Key Features & Architecture Highlights

### 🔑 1. Synchronized 27 Shared Requirement Keys
All 27 ecosystem fields (Role-based Aadhaar, PAN, Bank Details, NIC Activity Codes, Investment & Turnover, Employment, Declarations, GeM/TReDS/NCS preferences) are **100% harmonized** across 4 layers:
- **Database Engine** (`RequirementStatus` ORM)
- **Document Template Generator** (`template_generator.py`)
- **Conversational AI Intake Gatherer** (`ai_chat_engine.py`)
- **Vision OCR Document Extractor** (`ocr_extractor.py`)

### 📋 2. Create New Template & 9-Section Document Generator
- Generates official **9-section client requirement documents** (Identity, Business, Office Address, Units, Banking, Activity, Employment, Financials, Declarations).
- **Live Employee Editor**: Inline text editing, custom field addition, field deletion.
- **Multi-Format Exporting**: One-click **PDF Document** generation & formatted **Microsoft Word (.doc)** export.

### ⚡ 3. Gemini Vision OCR & Smart Client Data Entry Portal
- **Drag & Drop Upload Zone** for Aadhaar Cards, PAN Cards, and Bank Passbooks/Cheques.
- Auto-extracts client data via **Google Gemini 3.6 Flash Vision OCR** and displays glowing `⚡ Auto-filled` badges.
- Includes a live progress bar (`Completion: X / Y Core Fields`) and responsive input cards.

### 🤖 4. Gemini 3.6 Flash Conversational Requirement Gatherer
- Dynamically rephrases intake questions into friendly, human-like prompts via Google's Generative Language REST API (`v1beta`).
- Implements real-time input validation, error handling, and zero-fail fallback mechanisms.

---

## 🛠️ Technology Stack

| Layer | Technologies Used |
|---|---|
| **Frontend UI** | Next.js 14 App Router, TypeScript, Tailwind CSS, Lucide Icons, Glassmorphism Design System |
| **Backend API** | Python 3.12, FastAPI, Pydantic v2, Uvicorn, SQLAlchemy |
| **AI & Vision OCR** | Google Gemini 3.6 Flash (`models/gemini-3.6-flash`), REST API Integration |
| **Database** | SQLite (Default Dev) / PostgreSQL (Production) |
| **Containerization** | Docker, Docker Compose |

---

## 🚀 Quick Start & Local Setup

### Prerequisites
- **Python 3.12+** installed
- **Node.js 18+** installed
- **Google Gemini API Key** (Set in `.env`)

---

### 1. Clone & Configure Environment

```bash
git clone https://github.com/Aincuru-LLP/TAXLA-DOCUMENTS-AI.git
cd TAXLA-DOCUMENTS-AI
```

Create a `.env` file in the root folder:

```env
DATABASE_URL=sqlite:///./sql_app.db
GEMINI_API_KEY=your_gemini_api_key_here
PORT=8000
```

---

### 2. Standard Launcher (Runs Both Backend & Frontend)

```bash
python run.py
```

- **Frontend Application**: 👉 [http://localhost:3000](http://localhost:3000)
- **FastAPI Backend Service**: 👉 [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs**: 👉 [http://localhost:8000/docs](http://localhost:8000/docs)

---

### 3. Manual Server Setup (Optional)

#### **Start FastAPI Backend:**
```bash
python -m venv venv
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

#### **Start Next.js Frontend:**
```bash
cd frontend
npm install
npm run dev
```

---

## 🐳 Docker Deployment

To launch the complete containerized stack:

```bash
docker-compose up --build
```

- **Frontend Container**: `http://localhost:3000`
- **Backend Container**: `http://localhost:8000`

---

## 🧪 Testing & Verification Suite

Run full system unit and end-to-end integration tests:

```bash
# Run FastAPI Backend Unit Tests
python -m pytest tests/test_intake_system.py -v

# Run Full 9-Step E2E Integration Suite
python scripts/test_e2e_full_system.py
```

---

## 📡 Key API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | System health check & active engine status |
| `POST` | `/api/v1/cases` | Create a new MSME Udyam Case |
| `POST` | `/api/v1/cases/generate-template` | Generate 9-Section requirement template |
| `POST` | `/api/v1/cases/create-from-template` | Create case from filled template document |
| `POST` | `/api/v1/cases/{id}/documents` | Upload document & trigger Gemini Vision OCR |
| `GET` | `/api/v1/cases/{id}/chat/next-question` | Fetch next AI-generated intake question |
| `POST` | `/api/v1/cases/{id}/chat/answer` | Submit requirement answer & validate |
| `GET` | `/api/v1/cases/{id}/review` | Fetch case review summary & readiness status |
| `POST` | `/api/v1/cases/{id}/submit` | Final submission of completed Udyam Case |

---

## 📄 License & Attribution

Developed for **Aincuru LLP / Taxla AI Platform**. Authorized for official MSME Udyam Registration workflow processing.
