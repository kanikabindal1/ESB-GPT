#!/usr/bin/env python3
"""Add input and output schema columns to both API knowledge store JSON files."""

import json

# In-house APIs: id -> (input dict, output dict)
INHOUSE_SCHEMAS = {
    "api-store-location": (
        {"latitude": "number, optional", "longitude": "number, optional", "radius_km": "integer, optional", "filters": "object, optional"},
        {"stores": "array of store objects", "total_count": "integer"},
    ),
    "api-bank-check-balance": (
        {"account_number": "string, required", "bank_code": "string, required", "customer_id": "string, required"},
        {"verified": "boolean", "balance": "number", "currency": "string"},
    ),
    "api-sim-swaps": (
        {"msisdn": "string, required", "new_iccid": "string, required", "reason": "string, optional"},
        {"request_id": "string", "status": "string", "estimated_completion": "ISO datetime, optional"},
    ),
    "api-customer-status": (
        {"customer_id": "string, required"},
        {"status": "string", "segment": "string", "eligible_offers": "array of strings", "balance": "number"},
    ),
    "api-topup": (
        {"msisdn": "string, required", "amount": "number, required", "payment_ref": "string, required"},
        {"success": "boolean", "new_balance": "number", "receipt_id": "string"},
    ),
    "api-bill-pay": (
        {"bill_id": "string, required", "amount": "number, required", "payment_method": "string, required"},
        {"payment_id": "string", "status": "string", "paid_at": "ISO datetime"},
    ),
    "api-usage-consumption": (
        {"msisdn": "string, required", "period": "string, optional"},
        {"data_mb": "number", "voice_min": "number", "sms_count": "integer", "period_start": "ISO date"},
    ),
    "api-device-swap": (
        {"msisdn": "string, required", "new_imei": "string, required", "reason": "string, optional"},
        {"request_id": "string", "status": "string", "effective_at": "ISO datetime"},
    ),
    "api-mnp": (
        {"number": "string, required"},
        {"eligible": "boolean", "current_operator": "string", "estimated_days": "integer"},
    ),
    "api-otp-verification": (
        {"channel": "string, required", "destination": "string, required", "purpose": "string, optional"},
        {"otp_ref": "string", "expires_in_seconds": "integer", "masked_destination": "string"},
    ),
    "api-subscriber-registration": (
        {"msisdn": "string, required", "id_type": "string, required", "id_number": "string, required", "name": "string, required"},
        {"request_id": "string", "status": "string", "customer_id": "string"},
    ),
    "api-balance-inquiry": (
        {"msisdn": "string, required"},
        {"balance": "number", "currency": "string", "credit_limit": "number"},
    ),
    "api-bundle-purchase": (
        {"msisdn": "string, required", "bundle_id": "string, required", "payment_ref": "string, required"},
        {"success": "boolean", "bundle_code": "string", "valid_until": "ISO date", "remaining_mb": "number"},
    ),
    "api-roaming-status": (
        {"msisdn": "string, required"},
        {"roaming_active": "boolean", "current_country": "string", "pack": "string", "data_remaining_mb": "number"},
    ),
    "api-coverage-check": (
        {"latitude": "number, optional", "longitude": "number, optional", "address": "string, optional"},
        {"coverage": "string", "technologies": "array of strings", "signal_strength": "integer"},
    ),
    "api-complaints-tickets": (
        {"customer_id": "string, required", "category": "string, required", "subject": "string, required", "description": "string, required"},
        {"ticket_id": "string", "status": "string", "priority": "string", "created_at": "ISO datetime"},
    ),
    "api-payment-history": (
        {"customer_id": "string, required", "from_date": "ISO date, optional", "to_date": "ISO date, optional"},
        {"transactions": "array of transaction objects", "total_count": "integer"},
    ),
    "api-invoice-download": (
        {"invoice_id": "string, required", "format": "string, optional"},
        {"download_url": "string", "expires_at": "ISO datetime"},
    ),
    "api-plan-change": (
        {"msisdn": "string, required", "new_plan_id": "string, required", "effective_date": "ISO date, optional"},
        {"request_id": "string", "status": "string", "effective_from": "ISO date"},
    ),
    "api-loyalty-rewards": (
        {"customer_id": "string, required"},
        {"points_balance": "integer", "tier": "string", "expiring_soon": "integer"},
    ),
    "api-agent-commission": (
        {"agent_id": "string, required"},
        {"balance": "number", "pending": "number", "currency": "string", "last_payout": "ISO date"},
    ),
    "api-kyc-verification": (
        {"customer_id": "string, required", "id_type": "string, required", "document_ref": "string, required"},
        {"submission_id": "string", "status": "string", "estimated_completion": "ISO date"},
    ),
    "api-blacklist-fraud": (
        {"msisdn": "string, required"},
        {"blacklisted": "boolean", "risk_score": "integer", "last_checked": "ISO datetime"},
    ),
    "api-notification-preferences": (
        {"customer_id": "string, required"},
        {"sms": "boolean", "email": "boolean", "push": "boolean", "marketing_sms": "boolean"},
    ),
    "api-product-catalog": (
        {"category": "string, optional", "region": "string, optional"},
        {"products": "array of product objects"},
    ),
    "api-order-status": (
        {"order_id": "string, required"},
        {"order_id": "string", "status": "string", "tracking_number": "string", "eta": "ISO date"},
    ),
    "api-activation-provisioning": (
        {"iccid": "string, required", "imei": "string, required", "plan_id": "string, required"},
        {"request_id": "string", "msisdn": "string", "status": "string", "estimated_ready": "ISO datetime"},
    ),
    "api-partner-onboarding": (
        {"company_name": "string, required", "contact_email": "string, required", "apis_requested": "array of strings, required"},
        {"partner_id": "string", "status": "string", "client_id": "string"},
    ),
    "api-audit-activity": (
        {"customer_id": "string, required", "from": "ISO date, optional", "to": "ISO date, optional", "limit": "integer, optional"},
        {"events": "array of audit event objects"},
    ),
    "api-speed-test": (
        {"msisdn": "string, required", "test_type": "string, optional"},
        {"test_id": "string", "status": "string", "download_mbps": "number", "upload_mbps": "number", "latency_ms": "number"},
    ),
    "api-spending-summary": (
        {"customer_id": "string, required", "period": "string, required"},
        {"total_spend": "number", "breakdown": "object", "currency": "string"},
    ),
    "api-transaction-breakdown": (
        {"customer_id": "string, required", "from": "ISO date, optional", "to": "ISO date, optional"},
        {"transactions": "array of transaction objects"},
    ),
    "api-bill-breakdown": (
        {"bill_id": "string, required"},
        {"plan_fee": "number", "usage_charges": "number", "addons": "number", "discounts": "number", "total": "number"},
    ),
    "api-usage-cost": (
        {"msisdn": "string, required", "period": "string, optional"},
        {"data_cost": "number", "voice_cost": "number", "sms_cost": "number", "total_usage_cost": "number"},
    ),
    "api-monthly-spend": (
        {"customer_id": "string, required", "months": "integer, optional"},
        {"months": "array of { month, total } objects"},
    ),
    "api-budget-alerts": (
        {"customer_id": "string, required"},
        {"monthly_limit": "number", "alert_at_percent": "integer", "current_spend": "number", "alerts_enabled": "boolean"},
    ),
    "api-spend-by-category": (
        {"customer_id": "string, required", "period": "string, required"},
        {"plan": "number", "data": "number", "voice": "number", "sms": "number", "roaming": "number", "addons": "number"},
    ),
    "api-recharge-spend-history": (
        {"msisdn": "string, required", "limit": "integer, optional"},
        {"items": "array of { date, type, amount } objects"},
    ),
    "api-roaming-spend": (
        {"msisdn": "string, required", "period": "string, optional"},
        {"total_roaming_spend": "number", "by_country": "array of country spend objects"},
    ),
    "api-wallet-balance-spend": (
        {"customer_id": "string, required"},
        {"balance": "number", "pending": "number", "last_spend": "array of spend objects"},
    ),
}

# External APIs: id -> (input dict, output dict)
EXTERNAL_SCHEMAS = {
    "ext-azure-maps": (
        {"api-version": "string, required", "query": "string, required", "limit": "integer, optional"},
        {"results": "array of { position, address } objects"},
    ),
    "ext-google-maps-geocoding": (
        {"address": "string, optional", "latlng": "string, optional", "key": "string, required"},
        {"results": "array of { geometry, formatted_address } objects", "status": "string"},
    ),
    "ext-mapbox": (
        {"query": "string, required", "access_token": "string, required", "limit": "integer, optional"},
        {"features": "array of GeoJSON feature objects"},
    ),
    "ext-twilio-sms": (
        {"To": "string, required", "From": "string, required", "Body": "string, required"},
        {"sid": "string", "status": "string", "date_created": "string"},
    ),
    "ext-twilio-voice": (
        {"To": "string, required", "From": "string, required", "Url": "string, required"},
        {"sid": "string", "status": "string"},
    ),
    "ext-sendgrid": (
        {"personalizations": "array, required", "from": "object, required", "subject": "string, required", "content": "array, required"},
        {"statusCode": "integer", "body": "string"},
    ),
    "ext-stripe-payments": (
        {"amount": "integer, required", "currency": "string, required", "payment_method_types": "array, optional"},
        {"id": "string", "client_secret": "string", "status": "string"},
    ),
    "ext-openweathermap": (
        {"q": "string, optional", "lat": "number, optional", "lon": "number, optional", "appid": "string, required"},
        {"main": "object", "weather": "array", "dt": "integer"},
    ),
    "ext-exchange-rate": (
        {"base": "string, optional"},
        {"result": "string", "conversion_rates": "object"},
    ),
    "ext-rest-countries": (
        {"name": "string, optional", "code": "string, optional"},
        {"name": "object", "capital": "array", "currencies": "object", "region": "string"},
    ),
    "ext-jsonplaceholder": (
        {},
        {"userId": "integer", "id": "integer", "title": "string", "body": "string"},
    ),
    "ext-auth0": (
        {"grant_type": "string, required", "username": "string, optional", "password": "string, optional", "client_id": "string, required"},
        {"access_token": "string", "token_type": "string", "expires_in": "integer"},
    ),
    "ext-plaid": (
        {"access_token": "string, required", "options": "object, optional"},
        {"accounts": "array of { account_id, balances } objects"},
    ),
    "ext-github": (
        {"owner": "string, required", "repo": "string, required"},
        {"id": "integer", "full_name": "string", "private": "boolean", "html_url": "string"},
    ),
    "ext-slack": (
        {"channel": "string, required", "text": "string, required"},
        {"ok": "boolean", "channel": "string", "ts": "string"},
    ),
    "ext-microsoft-graph": (
        {},
        {"displayName": "string", "mail": "string", "id": "string"},
    ),
    "ext-here-geocoding": (
        {"q": "string, required", "apiKey": "string, required"},
        {"items": "array of { position, address } objects"},
    ),
    "ext-nominatim": (
        {"q": "string, required", "format": "string, optional"},
        {"lat": "string", "lon": "string", "display_name": "string"},
    ),
    "ext-paypal": (
        {"intent": "string, required", "purchase_units": "array, required"},
        {"id": "string", "status": "string", "links": "array"},
    ),
    "ext-firebase-auth": (
        {"email": "string, required", "password": "string, required", "returnSecureToken": "boolean, optional"},
        {"idToken": "string", "refreshToken": "string", "expiresIn": "string"},
    ),
    "ext-zoom": (
        {"topic": "string, required", "type": "integer, required", "start_time": "string, optional"},
        {"id": "integer", "join_url": "string", "start_url": "string"},
    ),
    "ext-aws-s3": (
        {"Bucket": "string, required", "Key": "string, required", "Body": "string or buffer, optional"},
        {"ETag": "string", "VersionId": "string, optional"},
    ),
    "ext-postman-echo": (
        {"foo": "string, optional"},
        {"args": "object", "headers": "object", "url": "string"},
    ),
    "ext-mailgun": (
        {"from": "string, required", "to": "string, required", "subject": "string, required", "text": "string, optional"},
        {"id": "string", "message": "string"},
    ),
    "ext-vonage-sms": (
        {"from": "string, required", "to": "string, required", "text": "string, required"},
        {"message-count": "string", "messages": "array"},
    ),
    "ext-ipinfo": (
        {"ip": "string, optional"},
        {"ip": "string", "city": "string", "region": "string", "country": "string"},
    ),
    "ext-ipify": (
        {},
        {"ip": "string"},
    ),
    "ext-unsplash": (
        {"query": "string, required", "per_page": "integer, optional"},
        {"results": "array of { id, urls, user } objects"},
    ),
    "ext-newsapi": (
        {"country": "string, optional", "apiKey": "string, required", "pageSize": "integer, optional"},
        {"status": "string", "totalResults": "integer", "articles": "array"},
    ),
}


def main():
    base = __file__.replace("add_input_output_schemas.py", "")

    for path, schemas, label in [
        (base + "api-knowledge-store.json", INHOUSE_SCHEMAS, "in-house"),
        (base + "external-apis-knowledge-store.json", EXTERNAL_SCHEMAS, "external"),
    ]:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        new_apis = []
        for api in data["apis"]:
            aid = api.get("id")
            inp, out = schemas.get(aid, ({"_note": "schema not defined"}, {"_note": "schema not defined"}))
            new_api = {}
            for k, v in api.items():
                new_api[k] = v
                if k == "sample_output":
                    new_api["input"] = inp
                    new_api["output"] = out
            if "input" not in new_api:
                new_api["input"] = inp
                new_api["output"] = out
            new_apis.append(new_api)
        data["apis"] = new_apis
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Updated {path} ({label}) with input/output schemas for {len(new_apis)} APIs.")


if __name__ == "__main__":
    main()
