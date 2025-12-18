# Developer shortcuts

Run all commands from the repo root in PowerShell.

## One-command dev
- `powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 -ResetDb` — frees ports 8000/5173, resets SQLite via `reset_db.py`, starts backend (uvicorn --reload) and frontend (npm run dev), then runs backend smoke checks. Use this whenever backend/frontend code changed.

## Smoke only
- `powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 -SmokeOnly` — does not touch running servers; only runs `backend/scripts/smoke_api.py` against http://127.0.0.1:8000 and fails on any red check.

## Troubleshooting
- Locked DB (WinError 32): `scripts/dev.ps1` already cleans up processes on 8000/5173 before reset. If the DB stays locked, re-run `-ResetDb`; then check any remaining process with `netstat -ano | findstr :8000` and stop it (`Stop-Process -Id <pid>` or `taskkill /F /T /PID <pid>`) before retrying.

## Definition of Done for a PR
- `scripts/dev.ps1 -SmokeOnly` must pass.
- If backend or frontend touched: `scripts/dev.ps1 -ResetDb` must pass.
- If frontend touched: `npm --prefix frontend run build` must pass.
- `pytest` output can be noisy; the smoke script is the gating check for local dev stability.
