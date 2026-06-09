# LynxAuth

**Sharp Identity. Real Face.**

Middleware API untuk otentikasi wajah anti-deepfake — Rust gateway + Python inference + PostgreSQL/pgvector.

## Arsitektur

```
Browser / Client ──► Demo UI (nginx :3000) ──► lynxauth-core (Rust/Axum :8080)
                                                    │
                                                    ▼
                                          inference-worker (FastAPI :8000)
                                                    │
                                                    ▼
                                          PostgreSQL + pgvector (:5432)
```

## Stack

| Komponen | Teknologi | Port |
|----------|-----------|------|
| **Demo UI** | nginx + HTML/CSS/JS | `:3000` |
| **API Gateway** | Rust + Axum + SQLx | `:8080` |
| **Inference Worker** | Python + FastAPI + ONNX Runtime + InsightFace | `:8000` |
| **Database** | PostgreSQL 16 + pgvector | `:5432` (host `:55432`) |

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

Stack siap dalam beberapa menit:
- **Demo GUI**: http://localhost:3000
- **Gateway API**: http://localhost:8080
- **Worker**: http://localhost:8000

## Demo GUI

`demo-ui/index.html` — interface web untuk demo face authentication:

- **Register** — upload/capture foto → enroll face embedding
- **Verify** — upload/capture foto → deteksi deepfake + face match
- **Audit Logs** — lihat history transaksi (X-API-Key: `change-me`)

Akses via browser di port `:3000` setelah `docker compose up`.

## Endpoints

**Gateway (`lynxauth-core`):**
- `GET /healthz`
- `POST /api/v1/auth/register` (multipart: `user_id` + `image`)
- `POST /api/v1/auth/verify` (multipart: `image`)
- `GET /api/v1/admin/logs` (header: `X-API-Key`)

**Worker (`inference-worker`):**
- `GET /healthz`
- `POST /infer/register`
- `POST /infer/verify`

## Status Fitur

| Fitur | Status | Backend |
|-------|--------|---------|
| Face Recognition | ✅ Real | InsightFace (ArcFace + SCRFD, CPU) |
| Deepfake Detection | ✅ Real | ONNX (deepfake_vit_int8) |
| Face Embedding Store | ✅ Real | PostgreSQL + pgvector |
| Audit Log | ✅ Real | PostgreSQL via SQLx (Rust) |
| Admin API Key Auth | ✅ Real | Middleware Axum |
| Rate Limiting | ⏳ Stub | TODO: sliding window |
| Camera Hardware Lock | ⏳ Basic | Name-based filter |
| Demo GUI | ✅ Baru | nginx + HTML/CSS/JS |

## Pengembangan Lokal

```bash
# Rust gateway
cd lynxauth-core && cargo run

# Python worker (butuh Postgres running)
cd inference-worker
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Tests
pytest tests -q
```

## Environment

Lihat `.env.example` untuk semua konfigurasi yang tersedia.
