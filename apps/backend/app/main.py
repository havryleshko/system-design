import logging
from fastapi import FastAPI, HTTPException
from app.agent.system_design.graph import _load_checkpointer
from app.routes.runs import runs_router

app = FastAPI()
logger = logging.getLogger("app.main")

@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/health/checkpointer")
def checkpointer_health():
    try:
        saver = _load_checkpointer()
        # setup() is idempotent and ensures the DB is reachable.
        saver.setup()
        return {"status": "ok"}
    except Exception as exc:
        logger.exception("Checkpointer health failed")
        raise HTTPException(status_code=503, detail=f"checkpointer unavailable: {exc}") from exc

app.include_router(runs_router)
# Removed threads_router - LangGraph API handles thread management via its built-in routes