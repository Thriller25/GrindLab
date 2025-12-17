# Developer shortcuts

Run all commands from the repo root in PowerShell.

## One-command dev loop
- `scripts/dev.ps1 -ResetDb` - kills ports 8000/5173, resets SQLite via `reset_db.py`, starts backend (uvicorn --reload) and frontend (npm run dev), then runs backend smoke checks. The script fails if smoke fails.

## Smoke checks only
- `scripts/dev.ps1 -SmokeOnly` - does not touch running servers; only runs `backend/scripts/smoke_api.py` against the existing backend at http://127.0.0.1:8000 and fails on any red check.
