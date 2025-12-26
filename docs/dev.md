# Developer shortcuts

Run all commands from the repo root in PowerShell.

## One-command dev (Docker, PostgreSQL)
- `docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build`
  - Starts PostgreSQL, backend (uvicorn --reload), frontend (Vite dev server)
  - Hot reload for backend & frontend (volumes mounted)
  - API: http://localhost:8000, Frontend: http://localhost:5173

## Smoke only
- `docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d` (if not running)
- `powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 -SmokeOnly`  runs `backend/scripts/smoke_api.py` against http://127.0.0.1:8000

## Troubleshooting
- Ports busy: stop processes on 8000/5173, or `docker-compose down` and rerun.
- DB reset: `docker-compose -f docker-compose.yml -f docker-compose.dev.yml down -v` then `up --build`.

## Definition of Done for a PR
- Smoke checks pass (`scripts/dev.ps1 -SmokeOnly` or `backend/scripts/smoke_api.py` against running dev stack).
- If backend or frontend touched: `docker-compose ... up --build` OK.
- If frontend touched: `npm --prefix frontend run build` passes.
