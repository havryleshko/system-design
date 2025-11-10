from fastapi import FastAPI
from app.routes.runs import runs_router

app = FastAPI()

@app.get("/")
def health():
    return {"status": "ok"}

app.include_router(runs_router)
# Removed threads_router - LangGraph API handles thread management via its built-in routes