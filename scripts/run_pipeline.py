"""Run the database-driven network pipeline once, in-process (no HTTP or login needed)."""
import os
import sys
import uuid

if os.path.exists("/app/app"):
    sys.path.insert(0, "/app")
else:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.db.session import SessionLocal  # noqa: E402
from app.repositories.pipeline import PipelineRunRepository  # noqa: E402
from app.schemas.optimization import NetworkRunRequest  # noqa: E402
from app.services.network import execute_network_run  # noqa: E402

if __name__ == "__main__":
    params = NetworkRunRequest().model_dump()
    with SessionLocal() as db:
        repo = PipelineRunRepository(db)
        if repo.active_network_run():
            sys.exit("A network run is already in progress.")
        run = repo.create(run_id=str(uuid.uuid4()), run_type="network", parameters=params,
                          triggered_by="system")
        run_id = run.id
    execute_network_run(SessionLocal, run_id, params)
    with SessionLocal() as db:
        run = PipelineRunRepository(db).get_by_id(run_id)
        print(f"Run {run_id}: {run.status} in {run.duration_seconds}s"
              + (f" — {run.error}" if run.error else ""))
