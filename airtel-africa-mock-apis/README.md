# Airtel Africa Mock APIs

40+ realistic mock APIs for the Airtel Africa domain. Use for integration testing, crawlers, or demos.

## Domains

- **KYC** – Nigeria NIN, Ghana GID, Uganda NIN, Tanzania NIDA, Rwanda NID, Face Match
- **Airtel Money** – Wallet open, P2P, cash-in/out, statement, limits, fee quote, merchant collect/settlement, wallet block, KYC tier/recheck
- **FX & Remittance** – FX rates, cross-border remittance
- **SIM** – SIM registration capture, registration status, regulatory daily report
- **Billers** – Biller catalog, bill fetch, bill pay
- **Agents** – Float balance, float top-up, agent onboarding
- **Fraud & Risk** – AML/PEP/sanctions screen, KYT score, fraud velocity, chargeback/dispute
- **Care** – Create complaint, get ticket status
- **Offers** – CVM offer eligibility, apply offer
- **Regulatory** – Mobile money transaction report, privacy request
- **Retail** – Voucher bulk, stock allocate, starter pack activate, sales lead
- **Misc** – DND preferences, tax compute, roaming bundle, offnet top-up, advance offer

## Run

```bash
cd airtel-africa-mock-apis
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- **API docs (Swagger):** http://localhost:8000/docs  
- **OpenAPI JSON:** http://localhost:8000/openapi.json  
- **Health:** http://localhost:8000/health  

## Crawler

These mock APIs return consistent JSON. A crawler can:

1. Call `GET /openapi.json` to discover all routes and schemas.
2. Call each endpoint with sample payloads and persist request/response in the api-registry JSON format.

All routes are under `/africa/v1/` prefix.
