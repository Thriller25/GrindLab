from fastapi import FastAPI

from app.routers import api_router, calc, calc_runs


app = FastAPI(title="GrindLab Backend", version="0.1.0")


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(api_router, prefix="/api")
app.include_router(calc.router)
app.include_router(calc_runs.router)
