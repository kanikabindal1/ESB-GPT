"""
Airtel Africa Mock APIs - 40+ realistic endpoints for KYC, Airtel Money, SIM, Billers, Agents, Fraud, Care, Offers, Regulatory, Retail.
Run: uvicorn main:app --reload
OpenAPI: http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import kyc, wallet, fx_remittance, sim, billers, agents, fraud_risk, care, offers, regulatory, retail, misc

app = FastAPI(
    title="Airtel Africa Mock APIs",
    description="Realistic mock APIs for Airtel Africa domain: KYC, Airtel Money, SIM registration, Billers, Agents, Fraud/Risk, Care, Offers, Regulatory, Retail.",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(kyc.router)
app.include_router(wallet.router)
app.include_router(fx_remittance.router)
app.include_router(sim.router)
app.include_router(billers.router)
app.include_router(agents.router)
app.include_router(fraud_risk.router)
app.include_router(care.router)
app.include_router(offers.router)
app.include_router(regulatory.router)
app.include_router(retail.router)
app.include_router(misc.router)


@app.get("/")
def root():
    return {"service": "Airtel Africa Mock APIs", "docs": "/docs", "openapi": "/openapi.json"}


@app.get("/health")
def health():
    return {"status": "ok"}
