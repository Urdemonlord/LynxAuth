# LynxAuth

Middleware API untuk otentikasi wajah anti-deepfake sesuai PRD di `docs/PRD.md`.

## Struktur

- `lynxauth-core/` — API gateway Rust + Axum
- `inference-worker/` — worker FastAPI untuk deepfake + face recognition
- `lynxauth-sdk/` — SDK Python untuk capture kamera dan kirim request
- `docker/postgres/init/` — init SQL PostgreSQL + pgvector
- `tests/` — smoke test scaffold

## Status scaffold

Scaffold ini fokus ke fondasi repo dan kontrak antar komponen:

- endpoint publik gateway sudah ada
- proxy gateway → worker sudah ada
- schema database awal sudah ada
- worker sudah pakai PostgreSQL + pgvector untuk persistence embedding
- face recognition phase 2 sudah mencoba backend nyata via InsightFace (CPU by default)
- deepfake detector phase 2 sudah mendukung backend ONNX nyata via `DEEPFAKE_MODEL_PATH`
- bundle default sekarang mengarah ke model `deepfake_vit_int8.onnx` + `preprocessor_config.json`
- jika model deepfake belum tersedia, worker fallback ke heuristic mode dan melaporkan backend fallback
- rate limiting dan admin auth masih skeleton yang aman untuk dilanjutkan

## Endpoint target

Gateway (`lynxauth-core`):
- `GET /healthz`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/verify`
- `GET /api/v1/admin/logs`

Worker (`inference-worker`):
- `GET /healthz`
- `POST /infer/register`
- `POST /infer/verify`

## Quick start

1. Copy env:

```bash
cp .env.example .env
```

2. Jalankan stack:

```bash
docker compose up --build
```

3. Health check:

```bash
curl http://localhost:8080/healthz
curl http://localhost:8000/healthz
```

4. PostgreSQL host access untuk dev lokal:

```bash
# host port dipetakan ke 55432 supaya tidak bentrok dengan Postgres lain di VPS
psql postgresql://lynxauth:lynxauth@127.0.0.1:55432/lynxauth
```

## Development

### Rust gateway

```bash
cd lynxauth-core
cargo run
```

### Python worker

```bash
cd inference-worker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Python SDK

```bash
cd lynxauth-sdk
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python meow_sdk.py --help
```

## Verifikasi scaffold

```bash
cd /home/meowlabs/lynxauth
python3 -m compileall inference-worker lynxauth-sdk tests
cargo check --manifest-path lynxauth-core/Cargo.toml
pytest tests -q
```

## Next implementation priority

1. Hubungkan `embedding_store.py` ke PostgreSQL + pgvector beneran
2. Implement EfficientNet deepfake detector
3. Implement InsightFace ArcFace + SCRFD
4. Tambahkan rate limiting beneran di gateway
5. Tambahkan admin API key middleware beneran
6. Tambahkan benchmark dan integration tests
