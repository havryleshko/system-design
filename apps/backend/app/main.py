import logging
import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.agent.system_design.graph import _load_checkpointer_async
from app.routes.threads import threads_router
from app.routes.clarifier import clarifier_router

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
except ModuleNotFoundError:
    # Sentry is optional in some dev/test environments.
    sentry_sdk = None  # type: ignore[assignment]
    FastApiIntegration = None  # type: ignore[assignment]

# Configure logging to output to stdout
_log_level_name = (os.getenv("LOG_LEVEL") or "INFO").upper()
_log_level = getattr(logging, _log_level_name, logging.INFO)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Set specific loggers (inherit from LOG_LEVEL unless explicitly overridden)
logging.getLogger("app").setLevel(_log_level)
logging.getLogger("app.routes.threads").setLevel(_log_level)
logging.getLogger("app.services.threads").setLevel(_log_level)

SENTRY_DSN = os.getenv("SENTRY_DSN") or ""
if SENTRY_DSN and sentry_sdk is not None and FastApiIntegration is not None:
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

# CORS is required for browser clients (Vercel app.systesign.com -> api.systesign.com).
_cors_raw = os.getenv("CORS_ALLOW_ORIGINS", "")
cors_allow_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()] or [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "https://app.systesign.com",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

app.include_router(threads_router)
app.include_router(clarifier_router)