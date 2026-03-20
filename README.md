# GovCA Full-Stack Image Validation System

<img align="right" width="370" height="290" src="https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExMDEzbHZ5ZTA3cHA1Y29xM2g5MWY3eXYyaTFkMnJhbDV3MG5nNWYydiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/l0K4n42JVSqqUvAQg/giphy.gif">
<img align="right" width="370" height="290" src="https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExN2Q0N29xMTJ3bjc2eG1ieng1YXJ0d2puMG00enVyNGNvb3c0bDh0bCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/qjY1UPzyE2mER9gNbB/giphy.gif">

> Rwanda National Digital Certification Center — https://www.govca.rw/apply/searchIndvdlProductList.sg

A production-ready, fully Dockerised system delivering:

- **mTLS PKI login** — client certificate + password authentication via Nginx
- **AI face detection** — OpenCV + MediaPipe: blur, brightness, face presence, eyes, ears, occlusion
- **Email notifications** — SMTP + Jinja2 HTML templates on reject/accept/NID update
- **National ID update flow** — confirmed after photo accepted, with audit trail
- **TestOps dashboard** — live Prometheus metrics, Chart.js charts, health checks, CI pipeline status
- **GitHub Actions CI/CD** — lint → test (matrix) → security scan → Docker build → smoke test → deploy

---

## Problem

The GovCA portal accepts passport photos at upload time with zero automated validation. Blurry, dark, or biometrically defective photos are only rejected during manual review 1–5 business days later. Users receive no feedback, causing abandonment, repeated bad submissions, and helpdesk overload.

---

## Solution

A middleware service integrated at the photo upload step that:
1. Validates image quality instantly (< 2 seconds)
2. Detects face, eyes, ears, and occlusion with MediaPipe landmarks
3. Sends a structured HTML email within 60 seconds of rejection
4. On acceptance, prompts NID update and confirms by email
5. Exposes a live TestOps dashboard with Prometheus metrics

---

## How To Run

### 1. Clone & setup

```bash
git clone https://github.com/your-org/govca-full.git
cd govca-full
cp .env.example .env
# Edit .env with your credentials
```

### 2. Generate mTLS certificates

```bash
bash scripts/gen_certs.sh certs
# Import certs/client/client.p12 into your browser (password: govca2024)
```

### 3. Start all services

```bash
docker compose up -d
```

Services started:
| Service | URL |
|---------|-----|
| App (via Nginx) | https://localhost |
| Login | https://localhost/auth/login |
| Upload | https://localhost/upload/ |
| TestOps Dashboard | https://localhost/dashboard/ |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin / govca2024) |

### 4. Run tests

```bash
# All tests
pytest tests/ -v --cov=app

# Unit only
pytest tests/unit/ -v

# Integration only
pytest tests/integration/ -v

# E2E flow
pytest tests/e2e/ -v
```

### 5. Create first admin user

```bash
docker compose exec app flask shell
>>> from app import db
>>> from app.models import User
>>> from werkzeug.security import generate_password_hash
>>> u = User(national_id="1199780000000001", email="admin@govca.rw",
...          password_hash=generate_password_hash("Admin1234!"), full_name="Admin")
>>> db.session.add(u); db.session.commit()
```

---

## Application Flow

```
User                  Nginx (mTLS)          Flask App             Email
 |                        |                     |                    |
 |--- HTTPS + cert ------->|                     |                    |
 |                        |-- verify cert ------>|                    |
 |                        |-- forward headers -->|                    |
 |<-- login OK (session) --|<--- 200 + token -----|                    |
 |                        |                     |                    |
 |--- upload photo ------->|--- POST /submit ---->|                    |
 |                        |               [OpenCV checks]            |
 |                        |            [MediaPipe detection]         |
 |                        |                     |                    |
 |  (if rejected)         |                     |-- send rejection -->|
 |<-- 422 + defect code --|<-- rejected ---------|                    |
 |                        |                     |   [HTML email]     |
 |                        |                     |                    |
 |  (if accepted)         |                     |-- send accepted --->|
 |<-- 200 + proceed URL --|<-- accepted ---------|                    |
 |                        |                     |                    |
 |--- update NID -------->|--- POST /nid/confirm>|                    |
 |                        |               [update DB]               |
 |<-- complete ------------|<--- 200 -----------|-- NID updated ----->|
```

---

## Project Structure

```
govca-full/
├── app/
│   ├── __init__.py              # App factory + Prometheus metrics
│   ├── config.py                # Dev / Prod / Test configs
│   ├── models/__init__.py       # User, Application, ImageCheck, AuditLog
│   ├── routes/
│   │   ├── auth.py              # UC-01: mTLS + password login, register, logout
│   │   ├── upload.py            # UC-02: image upload + AI detection pipeline
│   │   ├── nid.py               # NID update, cancel application
│   │   └── dashboard.py         # TestOps: live metrics, health, activity feed
│   ├── services/
│   │   ├── face_detection.py    # OpenCV + MediaPipe: 5 sequential checks
│   │   └── email_service.py     # Celery tasks + Flask-Mail + Jinja2 templates
│   ├── templates/
│   │   ├── auth/login.html
│   │   ├── upload/upload.html
│   │   ├── nid/update.html
│   │   ├── dashboard/index.html
│   │   └── email/
│   │       ├── image_rejected.html
│   │       ├── image_accepted.html
│   │       └── nid_updated.html
│   └── static/
│       ├── css/main.css
│       └── js/
│           ├── login.js
│           ├── upload.js
│           └── dashboard.js
├── tests/
│   ├── conftest.py
│   ├── unit/test_face_detection.py
│   ├── integration/test_routes.py
│   └── e2e/test_full_flow.py
├── certs/                       # Generated by scripts/gen_certs.sh
│   ├── ca/                      # Root CA
│   ├── server/                  # Server TLS cert
│   └── client/                  # mTLS client cert (.p12 for browser)
├── nginx/nginx.conf             # mTLS termination + reverse proxy
├── scripts/gen_certs.sh         # PKI certificate generation
├── ci/
│   └── prometheus.yml           # Prometheus scrape config
├── .github/workflows/ci.yml     # GitHub Actions: lint→test→security→docker→deploy
├── docker-compose.yml           # app + nginx + worker + postgres + redis + prometheus + grafana
├── Dockerfile                   # Multi-stage: builder → production → test
├── wsgi.py                      # Gunicorn entry point
├── requirements.txt
└── .env.example
```

---

## Environment & Tool Versions

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Runtime |
| Flask | 3.0.3 | Web framework |
| OpenCV | 4.9.0 | Image clarity checks |
| MediaPipe | 0.10.14 | Face/landmark detection |
| Gunicorn | 22.0.0 | ASGI server |
| Nginx | 1.25 | mTLS termination + proxy |
| PostgreSQL | 16 | Production database |
| Redis | 7 | Celery broker |
| Celery | 5.3.6 | Async email tasks |
| Prometheus | 2.51.0 | Metrics collection |
| Grafana | 10.4.0 | Metrics visualisation |
| Docker | 25+ | Containerisation |
| GitHub Actions | — | CI/CD (alternative to Jenkins) |

---

## URLs

| Resource | URL |
|----------|-----|
| GovCA Portal | https://www.govca.rw/apply/searchIndvdlProductList.sg |
| Document Upload | https://www.govca.rw/document/stepIndvdlDocument.sg |
| Password Reset | https://www.govca.rw/reissue/stepIndvdlReisue.sg |
| App Status | https://www.govca.rw/indvdl/applyDetails/form/applyInfo.sg |
| GitHub Repo | https://github.com/Ramjan0487/pki_digital_signature |
