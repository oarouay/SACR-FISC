# Digital Commerce Intelligence Platform (Autonomous MVP)

A high-throughput, autonomous intelligence platform designed to ingest candidate Facebook Pages, execute two-stage crawls (Quick vs. Deep), capture evidentiary provenance, extract deterministic commercial signals, and prioritize pages for human review with explainable scoring.

---

## 1. Core Architectural Principles

### 1.1 Complete Independence from External Registries (RNE)
- **Decoupled Verification**: The platform does **NOT** depend on RNE or any external fiscal registry to classify, score, or prioritize candidate pages.
- **Default Status**: Every discovered page is assigned `registry_verification_status = NOT_CHECKED`.
- **Neutrality**: `NOT_CHECKED` is strictly treated as an unverified status, never as an indicator of irregularity or non-compliance.
- **Manual Verification Helper**: An optional fixture-based mock registry tool and `PATCH /pages/{id}/registry-verification` endpoint are provided exclusively for authorized manual post-review cross-checks.

### 1.2 Autonomous Two-Stage Processing Pipeline
```
Candidate URLs (Manual POST or Bulk CSV)
                    │
                    ▼
          [crawl_targets Queue]  ◄─── (PostgreSQL: SELECT ... FOR UPDATE SKIP LOCKED)
                    │
                    ▼
         [python -m app.worker]  (Persistent Browser, isolated contexts)
                    │
                    ├──► [QUICK CRAWL] (10 posts, media blocked)
                    │           │
                    │           ▼
                    │    [Quick Commercial Score] (0–100 explainable)
                    │           │
                    │      ┌────┴────────────────────────┐
                    │      │ quick_score < 60            │ quick_score >= 60
                    │      ▼                             ▼
                    │  [COMPLETED / Archived]    [DEEP CRAWL] (75 posts, full evidence)
                    │                                    │
                    │                                    ▼
                    │                         [Signal Extraction Pipeline]
                    │                                    │
                    │                                    ▼
                    │                         [Review Priority Score]
                    │                         (0.45*Comm + 0.30*Tx + 0.25*Econ)
                    │                                    │
                    │                                    ▼
                    └────────────────────────► [Human Review Queue] (if score >= 75)
                                               (registry_status: NOT_CHECKED)
```

1. **Target Ingestion**: Normalizes URLs and deduplicates against existing records via `canonical_url`.
2. **PostgreSQL Target Queue**: Uses `SELECT ... FOR UPDATE SKIP LOCKED` so multiple workers claim jobs safely without race conditions or duplicate processing.
3. **Quick Crawl**: Fast, low-bandwidth crawl (`QUICK_POST_LIMIT=10`, heavy media aborted) to determine basic commercial presence.
4. **Deterministic Quick Commercial Score**: Explainable score (0–100) based on detected prices, products, order methods, delivery, payment terms, and contacts.
5. **Autonomous Promotion**: Candidates with `quick_score >= DEEP_CRAWL_THRESHOLD` (default 60.0) are automatically promoted to `DEEP` crawl mode.
6. **Deep Crawl & Evidence Preservation**: Scrolls up to 75 posts, preserves full page/post screenshots with SHA-256 provenance hashes.
7. **Explainable Review Priority Scoring**:
   $$\text{ReviewPriority} = 0.45 \times \text{CommercialActivity} + 0.30 \times \text{TransactionEvidence} + 0.25 \times \text{EconomicActivity}$$
8. **Human Review Queue**: Pages with `review_priority >= REVIEW_THRESHOLD` (default 75.0) are surfaced with itemized evidence reasons.

---

## 2. Technology Stack

- **Language & Runtime**: Python 3.12+
- **API Framework**: FastAPI & Pydantic v2
- **Crawler Worker**: Playwright for Python (persistent Chromium process, isolated browser contexts)
- **Job Queue & Storage**: PostgreSQL 16 & SQLAlchemy 2.0 (Asyncpg for API, Psycopg2 for Alembic)
- **Queueing Engine**: PostgreSQL native row locks (`FOR UPDATE SKIP LOCKED`)
- **Database Migrations**: Alembic
- **Containerization**: Docker Compose (PostgreSQL, FastAPI Backend, Crawler Worker)
- **Testing**: pytest & pytest-asyncio (30+ unit & integration tests)
- **Linter**: Ruff

---

## 3. Project Structure

```
digital-commerce-intelligence/
├── backend/
│   ├── alembic/              # Database migration scripts (0001_initial, 0002_target_queue)
│   ├── app/
│   │   ├── api/              # REST API routes (targets, review_queue, metrics, pages, etc.)
│   │   ├── collectors/       # BaseCollector & FacebookPageCollector (reusable browser)
│   │   │   └── facebook/     # FacebookPageAdapter, selectors, exceptions
│   │   ├── core/             # Configuration & logging
│   │   ├── db/               # SQLAlchemy Base & async session management
│   │   ├── evidence/         # File storage & SHA-256 provenance hashing
│   │   ├── extraction/       # Deterministic extractors (phones, prices, emails, URLs, terms)
│   │   ├── fiscal_registry/  # Decoupled mock fiscal registry fixtures
│   │   ├── ingestion/        # TargetSource, Normalizer, CSV & manual ingestion
│   │   ├── models/           # SQLAlchemy 2.0 database models
│   │   ├── queue/            # PostgreSQL TargetQueue (SKIP LOCKED)
│   │   ├── schemas/          # Pydantic v2 request/response schemas
│   │   ├── scoring/          # QuickCommercialScorer & ReviewPriorityScorer
│   │   ├── services/         # CrawlService & QueryService
│   │   ├── static/           # Web UI Dashboard (Target Queue, Review Queue, Metrics)
│   │   ├── main.py           # FastAPI application entrypoint
│   │   └── worker.py         # Autonomous Crawler Worker entrypoint
│   ├── tests/                # Automated pytest test suite
│   ├── Dockerfile
│   └── alembic.ini
├── data/
│   ├── evidence/             # Local evidence filesystem storage
│   └── fixtures/             # Mock fixtures & sample_100_targets.csv
├── docker-compose.yml
├── .env.example
├── pyproject.toml
├── Makefile
└── README.md
```

---

## 4. Quickstart with Docker Compose

### Step 1: Clone and configure environment
```bash
cp .env.example .env
```

### Step 2: Start PostgreSQL, REST API, and Crawler Worker
```bash
docker compose up -d --build
```

### Step 3: Access Platform Endpoints
- **Web Dashboard**: [http://localhost:8000/](http://localhost:8000/)
- **Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: `curl http://localhost:8000/health`
- **Operational Metrics**: `curl http://localhost:8000/metrics/summary`

---

## 5. API Endpoints Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/targets` | Enqueue a single candidate Facebook Page URL |
| `POST` | `/targets/import-csv` | Bulk import candidate URLs from CSV |
| `GET` | `/targets` | List targets in queue with status & mode filters |
| `GET` | `/targets/{id}` | Inspect target status, attempt count, and scores |
| `GET` | `/review-queue` | List pages prioritized for human review ($\ge 75.0$) |
| `GET` | `/metrics/summary` | Real-time queue, crawl, and scoring metrics |
| `GET` | `/pages` | List preserved Facebook pages |
| `GET` | `/pages/{id}` | View page details and contact metadata |
| `GET` | `/pages/{id}/scores` | Inspect explainable score breakdown and reasons |
| `PATCH`| `/pages/{id}/registry-verification`| Record optional manual registry check findings |
| `GET` | `/evidence/{id}/file` | View/download verified PNG screenshot artifact |

---

## 6. Running Automated Tests

```bash
# Execute unit and integration tests inside Docker
docker compose exec backend pytest -v

# Run linter
docker compose exec backend ruff check .
```
