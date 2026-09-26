from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.fiscal_registry.mock import mock_fiscal_registry
from app.fiscal_registry.models import FiscalRecord

router = APIRouter(prefix="/fiscal-registry", tags=["Fiscal Registry Placeholder"])


@router.get(
    "/search",
    response_model=dict[str, Any],
    summary="Search mock fiscal registry placeholder by phone, email, or business name",
)
async def search_fiscal_registry(
    phone: str | None = Query(None, description="Phone number to query (e.g. +21698123456)"),
    email: str | None = Query(None, description="Official email address to query"),
    business_name: str | None = Query(None, description="Business name keywords"),
) -> dict[str, Any]:
    if not phone and not email and not business_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one query parameter: phone, email, or business_name",
        )

    results: list[FiscalRecord] = []

    if phone:
        rec = mock_fiscal_registry.search_by_phone(phone)
        if rec:
            results.append(rec)

    if email:
        rec = mock_fiscal_registry.search_by_email(email)
        if rec and rec not in results:
            results.append(rec)

    if business_name:
        name_matches = mock_fiscal_registry.search_by_business_name(business_name)
        for r in name_matches:
            if r not in results:
                results.append(r)

    return {
        "query": {"phone": phone, "email": email, "business_name": business_name},
        "count": len(results),
        "results": [r.model_dump() for r in results],
    }
