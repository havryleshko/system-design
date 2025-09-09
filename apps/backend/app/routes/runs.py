from fastapi import APIRouter

router = APIRouter(prefix="/runs", tags=["runs"])

@router.post("")
def create_run():
    return {"id": "stub-run-id"}

@router.get("/{run_id}")
def get_run(run_id: str):
    return {"id": run_id, "status": "stub"}