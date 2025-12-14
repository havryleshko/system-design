import logging
import sys
from fastapi import FastAPI, HTTPException
from app.agent.system_design.graph import _load_checkpointer_async
from app.routes.runs import runs_router
from app.routes.threads import threads_router

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Set specific loggers
logging.getLogger("app").setLevel(logging.DEBUG)
logging.getLogger("app.routes.threads").setLevel(logging.DEBUG)
logging.getLogger("app.services.threads").setLevel(logging.DEBUG)

app = FastAPI()
logger = logging.getLogger("app.main")

@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/health/checkpointer")
async def checkpointer_health():
    try:
        saver = await _load_checkpointer_async()
        # setup() is idempotent and ensures the DB is reachable.
        await saver.setup()
        return {"status": "ok"}
    except Exception as exc:
        logger.exception("Checkpointer health failed")
        raise HTTPException(status_code=503, detail=f"checkpointer unavailable: {exc}") from exc

app.include_router(runs_router)
app.include_router(threads_router)