import logging
import os
import sys
from fastapi import FastAPI, HTTPException
from app.agent.system_design.graph import _load_checkpointer_async
from app.routes.runs import runs_router
from app.routes.threads import threads_router

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

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

SENTRY_DSN = os.getenv("SENTRY_DSN") or ""
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
        release=os.getenv("SENTRY_RELEASE") or None,
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.05")),
        profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.0")),
        integrations=[FastApiIntegration()],
        send_default_pii=False,
    )

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