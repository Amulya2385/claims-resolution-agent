from fastapi import FastAPI

from claims_resolution_agent.api.routes.agent_runs import (
    router as agent_runs_router,
)
from claims_resolution_agent.api.routes.approvals import (
    router as approvals_router,
)
from claims_resolution_agent.api.routes.audit_events import (
    router as audit_events_router,
)
from claims_resolution_agent.api.routes.claims import (
    router as claims_router,
)
from claims_resolution_agent.api.routes.customers import (
    router as customers_router,
)
from claims_resolution_agent.api.routes.decisions import (
    router as decisions_router,
)
from claims_resolution_agent.api.routes.evaluations import (
    router as evaluations_router,
)
from claims_resolution_agent.api.routes.policies import (
    router as policies_router,
)


app = FastAPI(
    title="Claims Resolution Agent API",
    description="Application backend for the Claims Resolution Agent.",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(claims_router)
app.include_router(approvals_router)
app.include_router(customers_router)
app.include_router(policies_router)
app.include_router(agent_runs_router)
app.include_router(decisions_router)
app.include_router(audit_events_router)
app.include_router(evaluations_router)