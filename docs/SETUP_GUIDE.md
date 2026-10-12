# Setup Guide — Phase 1 (Backend Foundation + Authentication)

This covers only what exists so far: the backend skeleton and auth system.
Mobile/RRR/Recycler/Admin frontends don't exist yet (later phases).

## Prerequisites
- Python 3.11+
- MongoDB running locally (or update `DATABASE_URL` to point elsewhere), **only needed if you want to run against real Mongo** — the test suite itself uses an in-memory mock and does not require a running `mongod`.

## 1. Install dependencies
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Configure environment
```bash
cp .env.example .env
# Edit .env: at minimum, set a real JWT_SECRET for anything beyond local dev.
```

## 3. Start MongoDB (real DB, for actually running the server)
```bash
mongod --dbpath /path/to/your/data/dir
```

## 4. Seed the demo admin account
This is safe to re-run — it only creates the admin user if it doesn't already exist; it never resets or deletes existing data.
```bash
python -m scripts.seed_admin
```

## 5. Run the API
```bash
uvicorn app.main:app --reload --port 8000
```
Check it's up: `curl http://localhost:8000/api/v1/health`

## 6. Try it
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin1234"}'
```

See `TESTING_GUIDE.md` for how to run the automated test suite.
