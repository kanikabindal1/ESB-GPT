"""SIM registration and regulatory SIM reports."""
from fastapi import APIRouter
from schemas import SimRegCaptureRequest, SimRegCaptureResponse, RegulatorySimReportQuery

router = APIRouter(prefix="/africa/v1/sim", tags=["SIM"])


@router.post("/register", response_model=SimRegCaptureResponse)
def sim_registration_capture(req: SimRegCaptureRequest):
    """Capture SIM registration package (ID, selfie, consent) per market regulation."""
    return SimRegCaptureResponse(case_id="SIMREG-001", status="under_review")


@router.get("/{msisdn}/registration/status")
def sim_reg_status(msisdn: str):
    """Query SIM registration and compliance status for a subscriber."""
    return {"registered": True, "last_update": "2025-11-10"}


@router.get("/regulatory/daily-report")
def regulatory_sim_daily_report(market: str, date: str | None = None):
    """Generate daily SIM registration compliance report per regulator template."""
    return {"file_url": "https://storage.company.com/simreg/NG/2025-02-18.csv"}
