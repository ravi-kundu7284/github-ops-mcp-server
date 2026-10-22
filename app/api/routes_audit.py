"""Audit log REST endpoints."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import verify_api_key
from app.models.schemas import OperationLog
from app.services.audit import get_audit_service

router = APIRouter(prefix="/api/operations", tags=["Audit & Operations"], dependencies=[Depends(verify_api_key)])


@router.get("", response_model=List[OperationLog])
async def list_operations(
    limit: int = Query(100, ge=1, le=500),
    channel: Optional[str] = Query(None, pattern="^(rest|mcp)$"),
    status: Optional[str] = Query(None, pattern="^(success|error|pending)$"),
) -> List[OperationLog]:
    """Retrieve history of executed operations across REST API and MCP server."""
    audit = get_audit_service()
    return audit.list_logs(limit=limit, channel=channel, status=status)


@router.delete("")
async def clear_operations() -> dict:
    """Clear all stored operation logs."""
    audit = get_audit_service()
    audit.clear()
    return {"success": True, "message": "Operation logs cleared"}
