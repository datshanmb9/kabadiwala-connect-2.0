# Testing Guide — Phase 1

## What has actually been executed, and where

The development sandbox used to write this code has **no network access and
no local MongoDB**, so `fastapi`, `motor`, `passlib`, `python-jose`,
`pytest`, and `mongomock-motor` could not be installed there, and no real
`mongod` could be started. Being upfront about exactly what that does and
doesn't mean for these tests:

**Actually run, in the sandbox, with a real interpreter (7/7 passing):**
- `tests/unit/test_rbac_core.py` — the pure role/ownership decision logic in
  `app/core/rbac_core.py` has zero external dependencies, so this file was
  genuinely executed with plain Python 3.12 and all 7 tests passed. Reproduce
  with: `python3 scripts/run_offline_unit_tests.py` (no pip install needed).
- Every `.py` file in the backend was also run through `python3 -m py_compile`
  to confirm it's syntactically valid — this catches typos/syntax errors but
  says nothing about runtime correctness of code that depends on missing
  packages.

**Written, but NOT executed anywhere yet — needs your environment:**
- `tests/unit/test_security.py` — needs `passlib[bcrypt]` and `python-jose`.
- `tests/integration/test_auth_api.py` — needs the full stack plus
  `mongomock-motor` (in-memory Mongo-compatible DB, no real `mongod` needed
  for this file specifically).

I have not claimed these pass. They're written to the same standard as the
tests that did run, but until one of us executes them, their status is
"written, expected to pass, unverified."

## How to run the full suite yourself
```bash
cd backend
pip install -r requirements.txt
pytest -v
```
This runs `test_rbac_core.py`, `test_security.py`, and `test_auth_api.py`
together. The integration tests use `mongomock-motor`, so you do **not**
need a running MongoDB instance just to run `pytest` — only for actually
starting the API server per `SETUP_GUIDE.md`.

If you'd rather validate against real MongoDB semantics before trusting,
e.g., the partial-unique-index behavior that Phase 2's bidding system will
rely on, point `tests/conftest.py`'s `test_db` fixture at a real
`motor.motor_asyncio.AsyncIOMotorClient` against a disposable test database
instead of `AsyncMongoMockClient` — mongomock's index enforcement is a
close but imperfect emulation of real MongoDB.

## Reporting convention for every phase going forward
Every phase will report, honestly:
- tests executed (and where — sandbox vs. your environment)
- tests passed / failed
- known limitations of the test environment
- anything written but not yet verified

"100% bug-free" will never be claimed without every relevant test having
actually passed somewhere real.
