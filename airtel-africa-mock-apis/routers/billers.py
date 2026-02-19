"""Africa biller catalog, bill fetch, and bill pay."""
from fastapi import APIRouter
from schemas import BillFetchRequest, BillFetchResponse, BillPayRequest, BillPayResponse

router = APIRouter(prefix="/africa/v1/billers", tags=["Billers"])


@router.get("")
def biller_catalog(market: str):
    """List utility/TV/education billers per market for Airtel Money payments."""
    return {
        "billers": [
            {"id": "UMEME", "type": "electricity", "name": "Umeme"},
            {"id": "KPLC", "type": "electricity", "name": "Kenya Power"},
            {"id": "ZESCO", "type": "electricity", "name": "ZESCO"},
        ]
    }


@router.post("/{biller_id}/fetch", response_model=BillFetchResponse)
def bill_fetch(biller_id: str, req: BillFetchRequest):
    """Fetch bill details for regional utilities and government services."""
    return BillFetchResponse(amount_due=1500.00, due_date="2025-03-05")


@router.post("/{biller_id}/pay", response_model=BillPayResponse)
def bill_pay(biller_id: str, req: BillPayRequest):
    """Pay bills via Airtel Money Africa and obtain receipt token."""
    return BillPayResponse(
        payment_id="BPY-001",
        status="success",
        receipt_url="https://receipts.company.com/bp/BPY-001.pdf",
    )
