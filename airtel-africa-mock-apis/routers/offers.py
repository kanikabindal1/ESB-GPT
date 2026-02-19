"""CVM offer eligibility and apply offer."""
from fastapi import APIRouter
from schemas import OfferEvaluateRequest, OfferEvaluateResponse

router = APIRouter(prefix="/africa/v1/offers", tags=["Offers"])


@router.post("/evaluate", response_model=OfferEvaluateResponse)
def cvm_offer_evaluate(req: OfferEvaluateRequest):
    """Evaluate customer for Africa-specific packs and mobile money offers."""
    return OfferEvaluateResponse(
        eligible_offers=["DATA-WEEK-2GB", "AMA-FREE-30", "VOICE-100MIN"]
    )


@router.post("/{offer_id}/apply")
def apply_offer(offer_id: str, msisdn: str):
    """Apply an eligible offer to subscriber."""
    return {"status": "applied", "offer_id": offer_id, "valid_until": "2025-03-19"}
