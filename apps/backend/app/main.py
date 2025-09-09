from fastapi import FastAPI
from app.routes.runs import router as runs_router

app = FastAPI()

@app.get("/")
def health():
    return {"status": "ok"}

app.include_router(runs_router)