from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from lokal_agent.core.config import AppConfig
from lokal_agent.core.storage.db import init_db, upsert_project, create_run, get_run, list_messages
from lokal_agent.core.agent.runner import run_agent, DummyAgent


cfg = AppConfig()
init_db(cfg)

app = FastAPI(title="Lokal-GbtAgent API")


class RunCreateIn(BaseModel):
    project_path: str
    start_message: str


@app.post("/runs")
def create_run_endpoint(payload: RunCreateIn):
    proj = upsert_project(cfg, payload.project_path)
    run = create_run(cfg, proj.id, payload.start_message)

    # For now run synchronously (simple + deterministic).
    # Later: queue/background worker.
    try:
        final = run_agent(cfg, DummyAgent(), run.id, payload.project_path, payload.start_message)
    except Exception as e:
        r = get_run(cfg, run.id)
        raise HTTPException(status_code=500, detail={"run_id": run.id, "status": r.status if r else "UNKNOWN", "error": str(e)})

    return {"run_id": run.id, "status": "COMPLETED", "final": final.model_dump()}


@app.get("/runs/{run_id}")
def get_run_endpoint(run_id: int):
    r = get_run(cfg, run_id)
    if not r:
        raise HTTPException(status_code=404, detail="run not found")
    return {
        "run_id": r.id,
        "project_id": r.project_id,
        "status": r.status,
        "start_message": r.start_message,
        "created_at": r.created_at,
        "finished_at": r.finished_at,
        "error": r.error,
    }


@app.get("/runs/{run_id}/messages")
def get_run_messages(run_id: int):
    r = get_run(cfg, run_id)
    if not r:
        raise HTTPException(status_code=404, detail="run not found")
    msgs = list_messages(cfg, run_id)
    return [{"role": m.role, "content": m.content, "ts": m.ts} for m in msgs]


def main():
    import uvicorn
    uvicorn.run("lokal_agent.api.main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
