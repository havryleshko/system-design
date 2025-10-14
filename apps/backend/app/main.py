from fastapi import FastAPI
from app.routes.runs import runs_router, threads_router

app = FastAPI()

@app.get("/")
def health():
    return {"status": "ok"}

app.include_router(runs_router)
app.include_router(threads_router)