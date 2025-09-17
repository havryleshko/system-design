from fastapi import APIRouter, status

router = APIRouter(prefix="/runs", tags=["runs"])

@router.post("", status_code=status.HTTP_201_CREATED)
def create_run():
    return {"id": "stub-run-id", "status": "queued"}

@router.get("/{run_id}")
def get_run(run_id: str):
    return {"id": run_id, "status": "queued"}
