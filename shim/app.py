"""FastAPI application for the Security Shim proxy service."""

from __future__ import annotations

from typing import Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import shim_settings
from .cost_model import FlatFeeCostModel, PerDestinationCostModel
from .credential_injector import CredentialInjector
from .escrow_gate import EscrowGate
from .models import ProxyRequest, ToolDefinition
from .proxy import ShimProxy
from .tool_registry import ToolRegistry

app = FastAPI(
    title="A2A Settlement Security Shim",
    version="0.1.0",
    description=(
        "Economic Air Gap proxy — escrow-gated, credential-injecting "
        "forward proxy for AI agent tool calls."
    ),
)

# ─── Singleton components ──────────────────────────────────────────────────

_escrow_gate = EscrowGate(
    cost_model=FlatFeeCostModel(shim_settings.default_cost),
    default_fee=shim_settings.default_cost,
)
_tool_registry = ToolRegistry()
_credential_injector = CredentialInjector()
_proxy = ShimProxy(
    escrow_gate=_escrow_gate,
    tool_registry=_tool_registry,
    credential_injector=_credential_injector,
)


def configure_vault(vault) -> None:
    """Attach a SecretVault instance (called during startup or tests)."""
    global _credential_injector, _proxy
    _credential_injector = CredentialInjector(vault=vault)
    _proxy = ShimProxy(
        escrow_gate=_escrow_gate,
        tool_registry=_tool_registry,
        credential_injector=_credential_injector,
    )


# ─── Request/Response schemas ─────────────────────────────────────────────


class ProxyRequestBody(BaseModel):
    escrow_id: str
    tool_id: Optional[str] = None
    destination_url: Optional[str] = None
    method: str = "POST"
    headers: dict[str, str] = Field(default_factory=dict)
    body: Optional[str] = None
    secret_id: Optional[str] = None


class RegisterEscrowBody(BaseModel):
    escrow_id: str
    amount: int
    status: str = "held"


class RegisterToolBody(BaseModel):
    tool_id: str
    destination_url: str
    method: str = "POST"
    secret_id: Optional[str] = None
    inject_as: str = "bearer"
    inject_key: str = "Authorization"
    cost_override: Optional[float] = None
    description: str = ""


# ─── Endpoints ─────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok", "service": "a2a-settlement-shim"}


@app.post("/shim/proxy")
async def proxy_request(
    req: ProxyRequestBody,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """Proxy an agent's tool call through the Economic Air Gap.

    Accepts either ``tool_id`` (full air gap) or ``destination_url`` (direct mode).
    """
    agent_id = None
    org_id = None

    # Extract agent identity from settlement auth token if present
    if hasattr(request.state, "settlement_token"):
        token = request.state.settlement_token
        agent_id = token.settlement_claims.agent_id
        org_id = token.settlement_claims.org_id

    proxy_req = ProxyRequest(
        escrow_id=req.escrow_id,
        tool_id=req.tool_id,
        destination_url=req.destination_url,
        method=req.method,
        headers=req.headers,
        body=req.body,
        secret_id=req.secret_id,
        agent_id=agent_id or "anonymous",
        org_id=org_id,
    )

    result = await _proxy.handle(proxy_req)

    return JSONResponse(
        status_code=result.status_code if result.status_code < 500 else 502,
        content={
            "status_code": result.status_code,
            "headers": result.headers,
            "body": result.body,
            "cost_charged": result.cost_charged,
            "escrow_remaining": result.escrow_remaining,
        },
    )


@app.post("/shim/escrows")
async def register_escrow(req: RegisterEscrowBody):
    """Register an escrow for tracking in the shim's gate."""
    _escrow_gate.register_escrow(
        escrow_id=req.escrow_id,
        amount=req.amount,
        status=req.status,
    )
    return {"registered": True, "escrow_id": req.escrow_id}


@app.get("/shim/escrows/{escrow_id}")
async def get_escrow_status(escrow_id: str):
    """Check escrow status and remaining balance in the shim."""
    status = _escrow_gate.get_status(escrow_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Escrow {escrow_id} not found")
    return {
        "escrow_id": status.escrow_id,
        "status": status.status,
        "amount": status.amount,
        "remaining": status.remaining,
    }


@app.post("/shim/tools")
async def register_tool(req: RegisterToolBody):
    """Register a tool mapping for full-air-gap mode."""
    tool = ToolDefinition(
        tool_id=req.tool_id,
        destination_url=req.destination_url,
        method=req.method,
        secret_id=req.secret_id,
        inject_as=req.inject_as,
        inject_key=req.inject_key,
        cost_override=req.cost_override,
        description=req.description,
    )
    _tool_registry.register(tool)
    return {"registered": True, "tool_id": req.tool_id}


@app.get("/shim/tools")
async def list_tools():
    """List all registered tool mappings."""
    tools = _tool_registry.list_tools()
    return {
        "tools": [
            {
                "tool_id": t.tool_id,
                "destination_url": t.destination_url,
                "method": t.method,
                "inject_as": t.inject_as,
                "cost_override": t.cost_override,
                "description": t.description,
            }
            for t in tools
        ]
    }


@app.delete("/shim/tools/{tool_id}")
async def unregister_tool(tool_id: str):
    """Remove a tool mapping."""
    _tool_registry.unregister(tool_id)
    return {"unregistered": True, "tool_id": tool_id}


@app.get("/shim/audit")
async def get_audit_log(limit: int = 50):
    """Retrieve recent shim audit entries."""
    entries = _proxy.audit_log[-limit:]
    return {
        "entries": [
            {
                "escrow_id": e.escrow_id,
                "agent_id": e.agent_id,
                "destination": e.destination,
                "method": e.method,
                "secret_id": e.secret_id,
                "status_code": e.status_code,
                "cost": e.cost,
                "timestamp": e.timestamp,
                "tool_id": e.tool_id,
                "error": e.error,
            }
            for e in entries
        ]
    }


if __name__ == "__main__":
    uvicorn.run(
        "shim.app:app",
        host=shim_settings.host,
        port=shim_settings.port,
        reload=False,
        log_level="info",
    )
