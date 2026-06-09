# Product Requirements Document (PRD)
## LynxAuth — Middleware API untuk Otentikasi Wajah Anti-Deepfake

**Versi:** 1.1.0  
**Tanggal:** Juni 2025  
**Author:** Meow Labs  
**Status:** Draft

---

## 1. Overview

### 1.1 Latar Belakang

Sistem otentikasi berbasis wajah semakin banyak digunakan di berbagai sektor, mulai dari absensi digital, verifikasi identitas, hingga akses kontrol. Namun, kemajuan teknologi AI generatif—khususnya deepfake—menciptakan ancaman serius terhadap integritas sistem otentikasi berbasis biometrik wajah.

LynxAuth hadir sebagai **Middleware API** yang menyediakan layanan otentikasi wajah real-time yang terlindungi dari serangan deepfake dan spoofing. Sistem ini dirancang dengan arsitektur dua lapis: **Rust/Axum** sebagai API gateway untuk performa dan konkurensi tinggi, dan **Python/FastAPI** sebagai inference worker yang menangani komputasi model AI.

### 1.2 Nama Proyek

| Atribut | Detail |
|---|---|
| Nama Produk | LynxAuth |
| Nama Organisasi | Meow Labs |
| Tagline | Sharp Identity. Real Face. |
| Repositori | `github.com/meow-labs/lynxauth` |

### 1.3 Tujuan Produk

1. Menyediakan layanan otentikasi wajah real-time melalui REST API dengan latensi rendah.
2. Mendeteksi dan menolak input wajah yang merupakan hasil manipulasi AI (deepfake).
3. Menyediakan SDK ringan untuk integrasi di sisi client (edge device).
4. Menghasilkan audit log setiap transaksi otentikasi untuk keperluan kepatuhan.

---

## 2. Scope

### 2.1 Dalam Ruang Lingkup (In-Scope)

- API Gateway berbasis **Rust (Axum)** untuk request handling, routing, validasi, rate limiting, dan audit log.
- Inference Worker berbasis **Python (FastAPI)** untuk komputasi model AI (EfficientNet + ArcFace).
- Deteksi deepfake menggunakan model pre-trained **EfficientNet** (biner: real/fake).
- Pengenalan wajah menggunakan **ArcFace** via InsightFace.
- Deteksi wajah lokal di sisi client menggunakan **MediaPipe** (dalam SDK).
- SDK Python (`lynxauth-sdk`) untuk enkapsulasi akuisisi gambar dari kamera hardware.
- Penyimpanan embedding wajah menggunakan **pgvector** (PostgreSQL).
- Audit log transaksi otentikasi.

### 2.2 Luar Ruang Lingkup (Out-of-Scope)

- Pelatihan ulang (retraining) model EfficientNet maupun ArcFace.
- Fine-tuning model pada dataset wajah Indonesia.
- Deployment ke infrastruktur skala produksi (cloud autoscaling, load balancer).
- Integrasi dengan sistem HR, ERP, atau third-party identity provider (IdP).
- Fitur mobile SDK (Android/iOS).

---

## 3. Target Pengguna

### 3.1 Primary User

| Persona | Deskripsi |
|---|---|
| Developer / IT Team | Mengintegrasikan LynxAuth ke sistem absensi, access control, atau verifikasi identitas internal perusahaan/sekolah. |
| Peneliti Akademis | Menggunakan LynxAuth sebagai baseline sistem otentikasi wajah anti-spoofing untuk penelitian. |

### 3.2 Secondary User

| Persona | Deskripsi |
|---|---|
| Pengguna Akhir | Karyawan atau pelajar yang menggunakan sistem absensi/akses berbasis LynxAuth (interaksi tidak langsung). |

---

## 4. Arsitektur Sistem

### 4.1 Gambaran Umum

```
[Edge Device / Client]
        |
   lynxauth-sdk (Python)
   ├── Camera Hardware Lock
   ├── MediaPipe Face Detection
   └── JPEG Capture → bytes
        |
        | HTTPS REST API (multipart/form-data)
        v
┌─────────────────────────────────┐
│   lynxauth-core (Rust / Axum)   │  ← API Gateway
│   ├── Request Validation        │
│   ├── Rate Limiting             │
│   ├── API Key Auth (admin)      │
│   ├── Audit Log (PostgreSQL)    │
│   └── Internal HTTP Proxy       │
└──────────────┬──────────────────┘
               │ Internal HTTP (localhost)
               v
┌─────────────────────────────────┐
│  inference-worker (Python /     │  ← Inference Worker
│  FastAPI)                       │
│   ├── EfficientNet-B0           │
│   │   └── REAL / FAKE           │
│   └── ArcFace + SCRFD           │
│       └── Embedding + Matching  │
└──────────────┬──────────────────┘
               │
               v
        PostgreSQL + pgvector
        (Embedding Store)
               │
               v
   Response: { authenticated, user_id,
               confidence, deepfake_detected,
               latency_ms }
```

### 4.2 Alasan Pemisahan Arsitektur

| Lapisan | Teknologi | Alasan |
|---|---|---|
| API Gateway | Rust + Axum | Konkurensi tinggi (async, zero-cost abstraction), latensi routing sangat rendah, memory-safe tanpa GC |
| Inference Worker | Python + FastAPI | Ekosistem AI (PyTorch, InsightFace) hanya tersedia stabil di Python; tidak perlu binding FFI yang kompleks |
| Database | PostgreSQL + pgvector | pgvector mendukung cosine similarity search secara native; cocok untuk skala MVP |

> **Catatan Akademis:** Pemisahan ini memungkinkan setiap komponen dievaluasi secara independen: performa gateway (Rust) diukur terpisah dari latensi inferensi (Python), sehingga bottleneck sistem dapat diidentifikasi dengan presisi.

### 4.3 Komponen Sistem

| Komponen | Teknologi | Peran |
|---|---|---|
| `lynxauth-sdk` | Python, OpenCV, MediaPipe | Client-side: akuisisi & preprocessing wajah |
| `lynxauth-core` | **Rust, Axum, SQLx** | API Gateway: routing, validasi, rate limit, audit log |
| `inference-worker` | Python, FastAPI, PyTorch | Inference: EfficientNet + ArcFace |
| Deepfake Detector | EfficientNet-B0 (pre-trained, FaceForensics++) | Klasifikasi biner real/fake |
| Face Recognizer | ArcFace via InsightFace | Ekstraksi embedding wajah 512-dim |
| Face Detector | SCRFD (dalam InsightFace) | Deteksi bounding box wajah |
| Database | PostgreSQL + pgvector | Penyimpanan embedding terdaftar |
| Audit Log | Tabel PostgreSQL (via SQLx) | Pencatatan setiap transaksi |

---

## 5. Fitur & Requirement

### 5.1 Functional Requirements

#### FR-01: Registrasi Wajah
- Sistem menerima gambar wajah dari SDK untuk proses enrollment.
- Gateway (Rust) memvalidasi format dan meneruskan ke inference worker.
- Inference worker mengekstrak embedding wajah dan menyimpannya di database.
- Satu `user_id` dapat memiliki maksimal 5 sampel embedding.

#### FR-02: Otentikasi Wajah
- Sistem menerima gambar wajah dari SDK.
- Gateway meneruskan ke inference worker untuk deepfake detection.
- Jika lolos, inference worker menjalankan face recognition dan matching.
- Gateway mencatat hasil ke audit log dan mengembalikan response ke client.

#### FR-03: Deteksi Deepfake
- Inference worker memfilter input menggunakan EfficientNet-B0 pre-trained.
- Output berupa label biner: `REAL` atau `FAKE`.
- Jika `FAKE`, proses berhenti dan gateway mengembalikan HTTP 403.

#### FR-04: Face Recognition & Matching
- Inference worker mengekstrak embedding 512-dimensi menggunakan ArcFace.
- Sistem melakukan cosine similarity search terhadap embedding terdaftar di pgvector.
- Threshold kesamaan dapat dikonfigurasi, default: **0.6**.

#### FR-05: Audit Log
- Gateway (Rust) mencatat setiap transaksi: timestamp, `user_id`, hasil, latensi, status deepfake.
- Log dapat diakses melalui endpoint admin dengan autentikasi API key.

#### FR-06: SDK — Camera Hardware Lock
- SDK mencegah penggunaan virtual camera (V4L2 loopback, OBS virtual cam) dengan memvalidasi device path fisik.
- SDK hanya mengakses kamera hardware yang terdeteksi sebagai perangkat fisik.

#### FR-07: Rate Limiting
- Gateway membatasi jumlah request per IP: default **10 req/menit** untuk `/auth/verify`.
- Request melebihi batas dikembalikan dengan HTTP 429.

### 5.2 Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-01 | Latensi end-to-end (SDK → response) | ≤ 2000 ms pada hardware standar |
| NFR-02 | Latensi gateway (Rust, routing only) | ≤ 10 ms |
| NFR-03 | Latensi inference worker (Python) | ≤ 1000 ms (CPU, tanpa GPU) |
| NFR-04 | False Acceptance Rate (FAR) | ≤ 1% |
| NFR-05 | False Rejection Rate (FRR) | ≤ 5% |
| NFR-06 | Throughput | ≥ 10 concurrent requests |
| NFR-07 | Keamanan transmisi | HTTPS wajib untuk deployment |

---

## 6. API Specification

### Base URL
```
https://{host}/api/v1
```

> Semua endpoint diterima oleh **lynxauth-core (Rust/Axum)**. Request yang memerlukan inferensi AI akan diteruskan secara internal ke **inference-worker (Python/FastAPI)** pada port lokal.

### Endpoints

#### `POST /auth/register`
Mendaftarkan wajah pengguna baru.

**Request:**
```
Content-Type: multipart/form-data
Body:
  - user_id: string (required)
  - image: file (JPEG/PNG, required)
```

**Response:**
```json
{
  "success": true,
  "user_id": "usr_001",
  "message": "Face enrolled successfully."
}
```

---

#### `POST /auth/verify`
Melakukan otentikasi wajah.

**Request:**
```
Content-Type: multipart/form-data
Body:
  - image: file (JPEG/PNG, required)
```

**Response (Authenticated):**
```json
{
  "authenticated": true,
  "user_id": "usr_001",
  "confidence": 0.87,
  "deepfake_detected": false,
  "latency_ms": 312
}
```

**Response (Deepfake Detected):**
```json
{
  "authenticated": false,
  "user_id": null,
  "confidence": null,
  "deepfake_detected": true,
  "latency_ms": 145
}
```

**HTTP Status Codes:**

| Code | Kondisi |
|---|---|
| 200 | Proses otentikasi selesai (termasuk gagal authenticate) |
| 400 | Request tidak valid (tidak ada wajah terdeteksi, format salah) |
| 403 | Deepfake terdeteksi |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

---

#### `GET /admin/logs`
Mengambil audit log transaksi.

**Headers:**
```
X-API-Key: {admin_api_key}
```

**Response:**
```json
{
  "logs": [
    {
      "id": 1,
      "timestamp": "2025-06-01T10:00:00Z",
      "user_id": "usr_001",
      "authenticated": true,
      "deepfake_detected": false,
      "latency_ms": 312
    }
  ]
}
```

---

## 7. Struktur Direktori Proyek

```
lynxauth/
├── lynxauth-core/              # API Gateway (Rust)
│   ├── Cargo.toml
│   ├── src/
│   │   ├── main.rs             # Entry point Axum
│   │   ├── routes/
│   │   │   ├── auth.rs         # /auth/register, /auth/verify
│   │   │   └── admin.rs        # /admin/logs
│   │   ├── middleware/
│   │   │   ├── rate_limit.rs   # Rate limiting
│   │   │   └── api_key.rs      # Admin API key auth
│   │   ├── services/
│   │   │   ├── proxy.rs        # Internal HTTP → inference-worker
│   │   │   └── audit_log.rs    # Audit log ke PostgreSQL
│   │   ├── db/
│   │   │   └── mod.rs          # SQLx connection pool
│   │   └── config.rs
│
├── inference-worker/           # Inference Worker (Python)
│   ├── main.py                 # Entry point FastAPI
│   ├── routes/
│   │   └── infer.py            # /infer/register, /infer/verify
│   ├── services/
│   │   ├── deepfake_detector.py   # EfficientNet inference
│   │   ├── face_recognizer.py     # ArcFace + SCRFD
│   │   └── embedding_store.py     # pgvector operations
│   ├── models/
│   │   └── efficientnet_b0_ff++.pth
│   └── requirements.txt
│
├── lynxauth-sdk/               # Client SDK (Python)
│   ├── meow_sdk.py
│   ├── camera.py               # Camera hardware lock
│   └── utils.py
│
├── tests/
│   ├── test_auth.py
│   ├── test_deepfake.py
│   └── test_performance.py     # Latency & throughput benchmark
│
├── docker-compose.yml          # Orkestrasi 3 service
├── docs/
│   └── PRD.md
└── README.md
```

---

## 8. Model & Dataset

### 8.1 EfficientNet-B0 (Deepfake Detector)

| Atribut | Detail |
|---|---|
| Arsitektur | EfficientNet-B0 |
| Sumber Model | Pre-trained (tidak dilakukan retraining dalam penelitian ini) |
| Dataset Pelatihan | FaceForensics++ (DeepFakes, Face2Face, FaceSwap, NeuralTextures) |
| Task | Binary Classification: REAL / FAKE |
| Input | Cropped face image, 224×224 px |
| Output | Probabilitas [0.0 – 1.0], threshold default: 0.5 |

### 8.2 ArcFace (Face Recognizer)

| Atribut | Detail |
|---|---|
| Arsitektur | ArcFace (ResNet-50 backbone) |
| Implementasi | InsightFace Python Library |
| Dataset Pelatihan | MS-Celeb-1M + VGGFace2 (oleh author InsightFace) |
| Output | Embedding vektor 512-dimensi |
| Similarity Metric | Cosine Similarity |

### 8.3 SCRFD (Face Detector)

| Atribut | Detail |
|---|---|
| Arsitektur | SCRFD-10GF |
| Implementasi | InsightFace (otomatis diunduh) |
| Fungsi | Deteksi bounding box wajah, 5-point landmark |

> **Catatan:** Penelitian ini tidak mencakup proses pelatihan maupun optimasi model deep learning. Ketiga model digunakan sebagai komponen pre-trained yang diintegrasikan ke dalam middleware LynxAuth.

---

## 9. Metrik Evaluasi

### 9.1 Metrik Akurasi Sistem

| Metrik | Deskripsi | Target |
|---|---|---|
| FAR (False Acceptance Rate) | % orang salah yang diterima | ≤ 1% |
| FRR (False Rejection Rate) | % orang benar yang ditolak | ≤ 5% |
| Deepfake Rejection Rate | % deepfake yang berhasil ditolak | ≥ 95% |

### 9.2 Metrik Performa Sistem

| Metrik | Komponen | Target |
|---|---|---|
| Latency Gateway | Rust/Axum (routing + validasi) | ≤ 10 ms |
| Latency Inference | Python (EfficientNet + ArcFace) | ≤ 1000 ms |
| Latency End-to-End | SDK → final response | ≤ 2000 ms |
| Throughput | Concurrent requests | ≥ 10 req/s |
| CPU Usage | Saat inferensi (inference-worker) | Dicatat sebagai data |

### 9.3 Skenario Pengujian

| Skenario | Deskripsi |
|---|---|
| Uji Normal | Input wajah asli pengguna terdaftar → harus authenticated |
| Uji Impostor | Input wajah orang lain → harus rejected |
| Uji Deepfake | Input gambar deepfake (dari dataset FaceForensics++) → harus rejected |
| Uji Photo Attack | Input foto dicetak / ditampilkan di layar → harus rejected |
| Uji Rate Limit | > 10 req/menit dari 1 IP → harus HTTP 429 |
| Uji Performa | 10–50 concurrent requests → ukur latensi & throughput |

---

## 10. Batasan Penelitian

1. Penelitian ini tidak mencakup proses pelatihan maupun optimasi model deep learning. Model ArcFace dan EfficientNet digunakan sebagai model pre-trained.
2. Pengujian sistem dilakukan pada lingkungan terkontrol (lokal/dev server) dan tidak mencakup deployment di infrastruktur skala produksi.
3. Model EfficientNet tidak dievaluasi secara spesifik terhadap representasi wajah etnis Indonesia.
4. SDK tidak mendukung platform mobile (Android/iOS) pada versi ini.
5. Camera hardware lock diuji pada lingkungan Linux/Ubuntu; kompatibilitas Windows/macOS tidak dijamin.
6. Sistem belum diuji terhadap serangan adversarial berbasis model generatif terbaru (e.g., latent diffusion deepfake).

---

## 11. Milestone & Timeline

| Fase | Deliverable | Estimasi |
|---|---|---|
| Fase 1 | Setup proyek: struktur folder, Docker Compose, koneksi DB | Minggu 1 |
| Fase 2 | `lynxauth-core` (Rust): skeleton Axum, routing, proxy ke worker | Minggu 2 |
| Fase 3 | `inference-worker` (Python): endpoint infer, integrasi EfficientNet | Minggu 3 |
| Fase 4 | `inference-worker`: integrasi ArcFace + SCRFD, pgvector matching | Minggu 4 |
| Fase 5 | `lynxauth-core`: rate limiting, audit log, API key middleware | Minggu 5 |
| Fase 6 | `lynxauth-sdk`: camera lock, capture, integrasi ke core | Minggu 6 |
| Fase 7 | Pengujian fungsional & evaluasi metrik (FAR, FRR, latency) | Minggu 7 |
| Fase 8 | Dokumentasi final, cleanup, laporan skripsi BAB 4 | Minggu 8 |

---

## 12. Tech Stack

| Layer | Teknologi |
|---|---|
| API Gateway | **Rust, Axum, Tokio, SQLx** |
| Inference Worker | Python, FastAPI, PyTorch, timm |
| Face Recognition | InsightFace (ArcFace + SCRFD) |
| Deepfake Detection | EfficientNet-B0 (pre-trained, FaceForensics++) |
| Database | PostgreSQL + pgvector |
| SDK | Python, OpenCV, MediaPipe |
| Containerization | Docker, Docker Compose |
| Testing | pytest, cargo test, locust (load testing) |
| Version Control | Git + GitHub |

---

## 13. Risiko & Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Model EfficientNet tidak tersedia publik dengan bobot FaceForensics++ | Tinggi | Gunakan checkpoint publik HuggingFace; alternatif: timm pretrained ImageNet sebagai fallback |
| Komunikasi internal Rust → Python menambah latensi overhead | Sedang | Gunakan Unix socket atau localhost HTTP; ukur dan catat sebagai data overhead |
| Complexity build Rust lebih tinggi dari FastAPI pure | Sedang | Manfaatkan pengalaman Axum dari proyek Samaryn; gunakan scaffold yang sudah familiar |
| pgvector lambat pada similarity search dataset besar | Rendah | Skala MVP < 1000 pengguna; catat sebagai keterbatasan di BAB 5 |
| Virtual camera loopback sulit dideteksi di semua OS | Sedang | Batasan SDK didokumentasikan; uji hanya pada Linux/Ubuntu |

---

*Dokumen ini adalah PRD resmi untuk proyek LynxAuth versi MVP (v1.1.0), mencakup kebutuhan akademis skripsi S1 Informatika dan fondasi produk open-source Meow Labs.*
