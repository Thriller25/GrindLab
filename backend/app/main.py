from fastapi import FastAPI

from app.routers import api_router


app = FastAPI(title="GrindLab Backend", version="0.1.0")


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(api_router, prefix="/api")
