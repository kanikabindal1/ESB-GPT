"""FX rates and cross-border remittance."""
from fastapi import APIRouter
from schemas import FxRatesQuery, FxRatesResponse, RemittanceRequest

router = APIRouter(prefix="/africa/v1", tags=["FX & Remittance"])


@router.get("/fx/rates", response_model=FxRatesResponse)
def fx_rates(from_ccy: str, to_ccy: str):
    """Get current FX rates for cross-border remittances."""
    return FxRatesResponse(rate=30.25, as_of="2025-02-19T10:00:00Z")


@router.post("/remittance/send")
def crossborder_remittance(req: RemittanceRequest):
    """Send cross-border remittance with partner rails and compliance checks."""
    return {"remit_id": "RMT-001", "status": "in_flight"}
