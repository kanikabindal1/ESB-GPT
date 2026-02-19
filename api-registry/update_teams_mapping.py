#!/usr/bin/env python3
"""
Update team names to function-based teams:
  Canvas - customer care/self care
  Stylus - data usage / APIs fetching from datalake
  Fractal - customer dimension and customer related
  Rubik - fraud management
  Data Science Team - APIs using AI models
  Airtel Money - all airtel money related
  KYC - all KYC related
  Retailer - services used by retailers
"""
import json
from collections import defaultdict

# API id -> new team name
TEAM_MAP = {
    # Canvas - customer care / self care
    "api-complaints-tickets": "Canvas",
    "api-care-complaints-africa": "Canvas",
    "api-notification-preferences": "Canvas",
    "api-dnd-africa": "Canvas",
    # Stylus - data usage / datalake
    "api-usage-consumption": "Stylus",
    "api-usage-cost": "Stylus",
    "api-payment-history": "Stylus",
    "api-transaction-breakdown": "Stylus",
    "api-spending-summary": "Stylus",
    "api-monthly-spend": "Stylus",
    "api-spend-by-category": "Stylus",
    "api-balance-inquiry": "Stylus",
    "api-roaming-status": "Stylus",
    "api-roaming-spend": "Stylus",
    "api-recharge-spend-history": "Stylus",
    "api-invoice-download": "Stylus",
    "api-bill-breakdown": "Stylus",
    "api-regulatory-sim-daily-report": "Stylus",
    "api-regulatory-mm-transaction-report": "Stylus",
    "api-airtelmoney-af-statement": "Stylus",
    "api-bill-fetch-africa": "Stylus",
    "api-tax-withholding-africa": "Stylus",
    "api-budget-alerts": "Stylus",
    # Fractal - customer dimension / customer related
    "api-customer-status": "Fractal",
    "api-subscriber-registration": "Fractal",
    "api-loyalty-rewards": "Fractal",
    "api-audit-activity": "Fractal",
    "api-africa-privacy-data-requests": "Fractal",
    "api-order-status": "Fractal",
    "api-mnp": "Fractal",
    # Rubik - fraud management
    "api-blacklist-fraud": "Rubik",
    "api-aml-pep-sanctions": "Rubik",
    "api-airtelmoney-af-kyt": "Rubik",
    "api-airtelmoney-af-chargeback-dispute": "Rubik",
    "api-fraud-velocity-africa": "Rubik",
    "api-sim-swaps": "Rubik",
    "api-device-swap": "Rubik",
    # Data Science Team - AI models
    "api-cvm-offers-africa": "Data Science Team",
    "api-kyc-af-face-match": "Data Science Team",
    "api-airtime-advance-africa": "Data Science Team",
    # Airtel Money
    "api-airtelmoney-af-wallet-open": "Airtel Money",
    "api-airtelmoney-af-kyc-tier-upgrade": "Airtel Money",
    "api-airtelmoney-af-p2p": "Airtel Money",
    "api-airtelmoney-af-merchant-qr": "Airtel Money",
    "api-airtelmoney-af-cashin": "Airtel Money",
    "api-airtelmoney-af-cashout": "Airtel Money",
    "api-airtelmoney-af-fx-rates": "Airtel Money",
    "api-crossborder-remittance": "Airtel Money",
    "api-airtelmoney-af-kyc-recheck": "Airtel Money",
    "api-airtelmoney-af-merchant-settlement": "Airtel Money",
    "api-airtelmoney-af-limits": "Airtel Money",
    "api-airtelmoney-af-fee-quote": "Airtel Money",
    "api-airtelmoney-af-wallet-block": "Airtel Money",
    "api-wallet-balance-spend": "Airtel Money",
    "api-biller-catalog-africa": "Airtel Money",
    "api-bill-pay-africa": "Airtel Money",
    "api-offnet-airtime-buy": "Airtel Money",
    "api-topup": "Airtel Money",
    "api-bill-pay": "Airtel Money",
    "api-bank-check-balance": "Airtel Money",
    # KYC
    "api-kyc-verification": "KYC",
    "api-kyc-ng-nin-verify": "KYC",
    "api-kyc-gh-gcard-verify": "KYC",
    "api-kyc-ug-nin-verify": "KYC",
    "api-kyc-tz-nida-verify": "KYC",
    "api-kyc-rw-nid-verify": "KYC",
    "api-sim-registration-capture": "KYC",
    "api-sim-reg-status": "KYC",
    "api-agent-kyc-onboard-africa": "KYC",
    # Retailer
    "api-store-location": "Retailer",
    "api-product-catalog": "Retailer",
    "api-agent-commission": "Retailer",
    "api-agent-float-balance": "Retailer",
    "api-agent-float-topup": "Retailer",
    "api-partner-onboarding": "Retailer",
    "api-voucher-bulk-generation": "Retailer",
    "api-stock-rollout-africa": "Retailer",
    "api-kits-starterpack-activation": "Retailer",
    "api-sales-lead-africa": "Retailer",
    "api-activation-provisioning": "Retailer",
    "api-otp-verification": "Retailer",  # used in retailer/agent flows
    # Network / other -> map to closest: coverage/speed/roaming bundle/fiber
    "api-coverage-check": "Stylus",
    "api-speed-test": "Stylus",
    "api-africa-roaming-bundle": "Airtel Money",
    "api-africa-fiber-feasibility": "Stylus",
    "api-plan-change": "Fractal",
    "api-bundle-purchase": "Airtel Money",
}


def main():
    base = __file__.replace("update_teams_mapping.py", "")
    path = base + "api-knowledge-store.json"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    unmapped = []
    for api in data["apis"]:
        aid = api.get("id")
        if aid in TEAM_MAP:
            api["team"] = TEAM_MAP[aid]
        else:
            unmapped.append(aid)

    if unmapped:
        print("Unmapped API ids (left unchanged):", unmapped)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("Updated api-knowledge-store.json with new team names.")

    # Regenerate teams.json from updated store
    by_team = defaultdict(lambda: {"apis": [], "owners": set(), "domains": set()})
    for api in data["apis"]:
        t = api["team"]
        by_team[t]["apis"].append({"id": api["id"], "name": api["name"]})
        by_team[t]["owners"].add(api["owner"])
        by_team[t]["domains"].add(api["domain"])

    team_descriptions = {
        "Canvas": "Customer care and self-care: complaints, tickets, notification and DND preferences.",
        "Stylus": "Data usage and APIs that fetch or aggregate data from the datalake: usage, balance, history, reports, statements, tax.",
        "Fractal": "Customer dimension and customer-related: profile, status, registration, loyalty, audit, privacy, order status, MNP.",
        "Rubik": "Fraud management: blacklist, AML/PEP/sanctions, KYT, chargebacks, SIM swap, device swap, fraud velocity.",
        "Data Science Team": "APIs that use AI/ML models: offer eligibility (CVM), face match, advance scoring.",
        "Airtel Money": "Airtel Money: wallets, P2P, cash-in/out, merchant, FX, remittance, billers, limits, fees, top-up.",
        "KYC": "KYC and identity verification: national IDs (NIN, GID, NIDA, NID), SIM registration, agent KYC onboarding.",
        "Retailer": "Services used by retailers: store location, catalog, orders, agent commission and float, vouchers, stock, starter packs, sales leads, activation.",
    }

    teams_list = []
    for name in sorted(by_team.keys()):
        v = by_team[name]
        summary = team_descriptions.get(name, "APIs owned by " + name + ".")
        teams_list.append({
            "id": name.lower().replace(" ", "-"),
            "name": name,
            "summary": summary,
            "what_they_do": summary,
            "api_count": len(v["apis"]),
            "apis": v["apis"],
            "owners": sorted(v["owners"]),
            "domains": sorted(v["domains"]),
        })

    out = {
        "_meta": {
            "source": "api-knowledge-store.json",
            "description": "Team summary by function (Canvas, Stylus, Fractal, Rubik, Data Science Team, Airtel Money, KYC, Retailer)",
            "last_updated": "2025-02-19",
            "total_teams": len(teams_list),
        },
        "teams": teams_list,
    }
    with open(base + "teams.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("Regenerated teams.json with", len(teams_list), "teams.")


if __name__ == "__main__":
    main()
