"""
Pydantic schemas for Airtel Africa mock APIs.
"""
from typing import Optional
from pydantic import BaseModel, Field


# --- KYC ---
class NinVerifyRequest(BaseModel):
    nin: str
    full_name: Optional[str] = None


class GidVerifyRequest(BaseModel):
    gid: str


class NidaVerifyRequest(BaseModel):
    nida: str


class NidVerifyRequest(BaseModel):
    nid: str


class FaceMatchRequest(BaseModel):
    id_photo: str  # base64
    selfie: str  # base64


class KycVerifyResponse(BaseModel):
    valid: bool
    name: Optional[str] = None
    dob: Optional[str] = None
    match_score: Optional[float] = None


class FaceMatchResponse(BaseModel):
    match: bool
    liveness: float


# --- Wallet / Airtel Money ---
class WalletOpenRequest(BaseModel):
    msisdn: str
    id_type: str
    id_number: str


class WalletOpenResponse(BaseModel):
    wallet_id: str
    status: str
    kyc_level: str


class P2PRequest(BaseModel):
    from_wallet: str
    to_msisdn: str
    amount: float
    currency: str


class CashInRequest(BaseModel):
    wallet_id: str
    agent_id: str
    amount: float
    currency: str


class CashOutRequest(BaseModel):
    wallet_id: str
    agent_id: str
    amount: float
    currency: str


class TransferResponse(BaseModel):
    txn_id: str
    status: str
    fee: Optional[float] = None


class StatementQuery(BaseModel):
    wallet_id: str
    from_date: Optional[str] = None
    to_date: Optional[str] = None


class LimitsResponse(BaseModel):
    daily: float
    monthly: float
    currency: str


class FeeQuoteRequest(BaseModel):
    market: str
    type: str
    amount: float
    currency: str


class FeeQuoteResponse(BaseModel):
    fee: float
    total: float


class MerchantCollectRequest(BaseModel):
    merchant_id: str
    amount: float
    currency: str
    order_ref: str


class MerchantCollectResponse(BaseModel):
    payment_id: str
    status: str
    qr_png: str


class FxRatesQuery(BaseModel):
    from_ccy: str
    to_ccy: str


class FxRatesResponse(BaseModel):
    rate: float
    as_of: str


class RemittanceRequest(BaseModel):
    from_wallet: str
    to_msisdn: str
    amount: float
    from_ccy: str
    to_ccy: str


class WalletBlockRequest(BaseModel):
    wallet_id: str
    action: str
    reason: Optional[str] = None


class WalletBlockBody(BaseModel):
    action: str
    reason: Optional[str] = None


# --- SIM / Registration ---
class SimRegCaptureRequest(BaseModel):
    msisdn: str
    id_type: str
    id_number: str
    selfie: Optional[str] = None


class SimRegStatusResponse(BaseModel):
    registered: bool
    last_update: str


class SimRegCaptureResponse(BaseModel):
    case_id: str
    status: str


class RegulatorySimReportQuery(BaseModel):
    market: str
    date: Optional[str] = None


# --- Billers ---
class BillerCatalogQuery(BaseModel):
    market: str


class BillFetchRequest(BaseModel):
    biller_id: str
    identifier: str


class BillPayRequest(BaseModel):
    biller_id: str
    wallet_id: str
    amount: float
    currency: str


class BillFetchResponse(BaseModel):
    amount_due: float
    due_date: str


class BillPayResponse(BaseModel):
    payment_id: str
    status: str
    receipt_url: str


# --- Agents ---
class AgentFloatResponse(BaseModel):
    balance: float
    currency: str
    low_threshold: float


class AgentFloatTopUpRequest(BaseModel):
    agent_id: str
    amount: float
    currency: str


class AgentOnboardRequest(BaseModel):
    legal_name: str
    country: str
    kyc_docs: list[str]


class AgentOnboardResponse(BaseModel):
    agent_id: str
    status: str


# --- Fraud / Risk ---
class AmlScreenRequest(BaseModel):
    full_name: str
    dob: Optional[str] = None
    country: Optional[str] = None


class KytScoreRequest(BaseModel):
    wallet_id: str
    amount: float
    merchant: Optional[str] = None


class FraudVelocityRequest(BaseModel):
    msisdn: str


class RiskResponse(BaseModel):
    hit: Optional[bool] = None
    reference: Optional[str] = None
    risk_score: Optional[int] = None
    risk: Optional[float] = None
    flags: Optional[list[str]] = None
    signals: Optional[list[str]] = None


# --- Care ---
class ComplaintRequest(BaseModel):
    customer_id: str
    category: str
    description: str


class ComplaintResponse(BaseModel):
    ticket_id: str
    status: str


# --- Offers / CVM ---
class OfferEvaluateRequest(BaseModel):
    msisdn: str
    context: Optional[dict] = None


class OfferEvaluateResponse(BaseModel):
    eligible_offers: list[str]


# --- Regulatory ---
class PrivacyRequest(BaseModel):
    customer_id: str
    type: str


class RegulatoryReportQuery(BaseModel):
    market: str
    period: str


# --- Retail / Distribution ---
class VoucherBulkRequest(BaseModel):
    count: int
    denomination: float
    currency: str


class StockAllocateRequest(BaseModel):
    batch_id: str
    to: str
    quantity: int


class StarterPackActivateRequest(BaseModel):
    msisdn: str
    kit_code: str


class SalesLeadRequest(BaseModel):
    customer_name: str
    lead_type: str
    market: str


# --- Misc ---
class DndPreferencesRequest(BaseModel):
    msisdn: str
    categories: list[str]


class TaxComputeRequest(BaseModel):
    market: str
    amount: float
    service: str


class RoamingBundleRequest(BaseModel):
    msisdn: str
    bundle_code: str


class GenericIdResponse(BaseModel):
    id: Optional[str] = None
    status: str
    message: Optional[str] = None
