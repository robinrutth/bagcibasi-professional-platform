# Bagcibasi Lojistik AI

![CI](https://github.com/bagcibasi/bagcibasi-professional-platform/actions/workflows/ci.yml/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-70%25%2B-brightgreen)

Bagcibasi Lojistik AI; operasyon, musteri, karbon/ESG ve finans sureclerini tek panelde izlemek icin hazirlanan Next.js + FastAPI + PostgreSQL platformudur. Backend rol bazli JWT auth kullanir, frontend yonetici paneli sunar, Docker Compose tum servisleri birlikte ayaga kaldirir.

## Kurulum

```bash
cp .env.example .env
docker compose up --build
```

Servisler:

- Frontend: http://localhost
- Backend API docs: http://localhost/api/docs veya backend dogrudan calisirsa http://localhost:8000/docs
- PostgreSQL: `localhost:5432`

## Environment Variables

- `POSTGRES_DB`: PostgreSQL veritabani adi.
- `POSTGRES_USER`: PostgreSQL kullanici adi.
- `POSTGRES_PASSWORD`: PostgreSQL sifresi.
- `DATABASE_URL`: Backend SQLAlchemy baglanti adresi.
- `SECRET_KEY` / `APP_SECRET_KEY`: JWT ve uygulama gizli anahtarlari.
- `ALGORITHM`: JWT algoritmasi, varsayilan `HS256`.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Access token omru.
- `CORS_ORIGINS`: Virgulle ayrilmis izinli frontend origin listesi.
- `OPENAI_API_KEY`: AI ozellikleri icin opsiyonel anahtar.
- `SEED_DEMO_DATA`: `true` ise backend acilisinda demo veri seed eder.
- `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_API_BASE_URL`: Frontend API base URL degerleri.

## Test

Backend testleri production veritabanindan izole SQLite in-memory veritabaniyla calisir.

```bash
cd backend
pip install -r requirements.txt
pytest --cov=app --cov-report=term-missing --cov-fail-under=70
```

Frontend:

```bash
cd frontend
npm install
npm run lint
npm run build
```

Tum Docker imajlarini dogrulamak icin:

```bash
docker compose build
```

## API

Swagger/OpenAPI dokumani calisan backend uzerinde `/docs` adresindedir.

Ana endpointler:

- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/v1/shipments`
- `POST /api/v1/shipments`
- `GET /api/v1/customers`
- `GET /api/v1/carbon/summary`
- `POST /api/v1/carbon/calculate`
- `GET /health`

## Mimari

```text
                 +------------------+
                 |     Browser      |
                 +---------+--------+
                           |
                           v
                 +------------------+
                 |      Nginx       |
                 +----+--------+----+
                      |        |
          static/app  |        | /api, /docs, /health
                      v        v
              +------------+  +----------------+
              |  Next.js   |  |    FastAPI     |
              | frontend   |  | backend        |
              +------------+  +-------+--------+
                                      |
                                      v
                              +---------------+
                              |  PostgreSQL   |
                              +---------------+
```

## CI/CD

GitHub Actions `.github/workflows/ci.yml` her `main` ve `develop` branch push/pull request olayinda calisir. Pipeline backend testlerini coverage ile kosar, frontend lint/build adimlarini calistirir ve Docker Compose build sonucunu dogrular. Basarisiz test, lint veya build adimi pipeline'i bloklar.
