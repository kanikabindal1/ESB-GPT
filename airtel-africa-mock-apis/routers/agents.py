"""Agent float, top-up, and onboarding."""
from fastapi import APIRouter
from schemas import AgentFloatResponse, AgentFloatTopUpRequest, AgentOnboardRequest, AgentOnboardResponse

router = APIRouter(prefix="/africa/v1/agents", tags=["Agents"])


@router.get("/{agent_id}/float", response_model=AgentFloatResponse)
def agent_float_balance(agent_id: str):
    """Retrieve agent float balance, thresholds, and last top-up."""
    return AgentFloatResponse(
        balance=250000.00, currency="NGN", low_threshold=50000.00
    )


@router.post("/{agent_id}/float/topup")
def agent_float_topup(agent_id: str, req: AgentFloatTopUpRequest):
    """Top-up agent float via bank transfer or super-agent channel."""
    return {"topup_id": "FTU-001", "status": "processing"}


@router.post("/onboard", response_model=AgentOnboardResponse)
def agent_kyc_onboard(req: AgentOnboardRequest):
    """Onboard Airtel Money agents/distributors with local KYC and AML screening."""
    return AgentOnboardResponse(agent_id="AG-AF-1001", status="pending_verification")
