"""Airtel Money Africa - wallet, P2P, cash-in/out, merchant, FX, remittance, limits."""
from fastapi import APIRouter
from schemas import (
    WalletOpenRequest,
    WalletOpenResponse,
    P2PRequest,
    CashInRequest,
    CashOutRequest,
    TransferResponse,
    LimitsResponse,
    FeeQuoteRequest,
    FeeQuoteResponse,
    MerchantCollectRequest,
    MerchantCollectResponse,
    RemittanceRequest,
    WalletBlockBody,
)

router = APIRouter(prefix="/africa/v1/airtelmoney", tags=["Airtel Money"])


@router.post("/wallets", response_model=WalletOpenResponse)
def wallet_open(req: WalletOpenRequest):
    """Open mobile money wallet with market-specific KYC checks."""
    return WalletOpenResponse(wallet_id="WAF-123", status="active", kyc_level="tier1")


@router.post("/p2p", response_model=TransferResponse)
def p2p_transfer(req: P2PRequest):
    """Peer-to-peer wallet transfer within country."""
    return TransferResponse(txn_id="AMAF-001", status="success", fee=1.50)


@router.post("/cashin", response_model=TransferResponse)
def cash_in(req: CashInRequest):
    """Deposit cash at agent to wallet."""
    return TransferResponse(txn_id="CIN-001", status="success")


@router.post("/cashout", response_model=TransferResponse)
def cash_out(req: CashOutRequest):
    """Withdraw cash at agent."""
    return TransferResponse(txn_id="COT-001", status="success", fee=1.00)


@router.get("/wallet/{wallet_id}/statement")
def wallet_statement(wallet_id: str, from_date: str | None = None, to_date: str | None = None):
    """Wallet ledger and statement export."""
    return {
        "entries": [
            {"date": "2025-02-18", "type": "debit", "amount": 15.00, "ccy": "KES"},
            {"date": "2025-02-17", "type": "credit", "amount": 200.00, "ccy": "KES"},
        ],
        "closing_balance": 850.00,
    }


@router.get("/limits", response_model=LimitsResponse)
def get_limits(wallet_id: str):
    """Query limits by KYC tier and market."""
    return LimitsResponse(daily=1000.00, monthly=5000.00, currency="RWF")


@router.post("/fees/quote", response_model=FeeQuoteResponse)
def fee_quote(req: FeeQuoteRequest):
    """Quote fees for transfers, cash-in/out, bill pay."""
    return FeeQuoteResponse(fee=10.00, total=510.00)


@router.post("/merchant/collect", response_model=MerchantCollectResponse)
def merchant_collect(req: MerchantCollectRequest):
    """Dynamic QR collect for merchant acceptance."""
    return MerchantCollectResponse(
        payment_id="PMT-1001", status="pending", qr_png="base64..."
    )


@router.put("/wallets/{wallet_id}/kyc-tier")
def kyc_tier_upgrade(wallet_id: str, target_tier: str):
    """Upgrade wallet KYC tier (tier1→tier2→tier3)."""
    return {"status": "pending_review"}


@router.post("/kyc/recheck")
def kyc_recheck(wallet_id: str):
    """Periodic KYC screening for active wallets."""
    return {"status": "scheduled", "due_on": "2025-06-01"}


@router.put("/wallets/{wallet_id}/status")
def wallet_block(wallet_id: str, req: WalletBlockBody):
    """Block or unblock wallet upon risk or customer request."""
    return {"status": "blocked"}


@router.post("/merchant/settlement")
def merchant_settlement(merchant_id: str, amount: float, currency: str, bank_account: str):
    """Settle merchant collections to bank accounts."""
    return {"settlement_id": "STL-001", "status": "queued"}
