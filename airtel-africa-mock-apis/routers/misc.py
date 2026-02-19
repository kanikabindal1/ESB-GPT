"""DND, tax, roaming, top-up offnet."""
from fastapi import APIRouter
from schemas import DndPreferencesRequest, TaxComputeRequest, RoamingBundleRequest

router = APIRouter(prefix="/africa/v1", tags=["Misc"])


@router.put("/preferences/dnd")
def dnd_preferences(req: DndPreferencesRequest):
    """Set/Update DND preferences per regulator category for African markets."""
    return {"updated": True, "effective_at": "2025-02-20T00:00:00Z"}


@router.get("/preferences/dnd/{msisdn}")
def get_dnd_preferences(msisdn: str):
    """Get current DND preferences for a subscriber."""
    return {"msisdn": msisdn, "categories": ["promotions", "surveys"], "opt_out": True}


@router.post("/tax/compute")
def tax_compute(req: TaxComputeRequest):
    """Compute country-specific taxes/levies (excise/VAT on telecom services)."""
    return {"tax": 1200.00, "net": 8800.00}


@router.post("/roaming/bundles/purchase")
def roaming_bundle_purchase(req: RoamingBundleRequest):
    """Purchase intra-Africa roaming packs with fair-usage and partner network sync."""
    return {"success": True, "valid_until": "2025-02-26T00:00:00Z"}


@router.post("/topup/offnet")
def offnet_airtime_buy(wallet_id: str, dest_msisdn: str, amount: float, currency: str):
    """Allow Airtel Money users to buy airtime/data for other networks (where permitted)."""
    return {"txn_id": "TOP-OF-001", "status": "success"}


@router.post("/advance/offer")
def airtime_advance_offer(msisdn: str):
    """Offer small-ticket airtime/data loans (advance) with scorecards and recovery."""
    return {"eligible": True, "offer_amount": 100.00, "currency": "NGN"}
