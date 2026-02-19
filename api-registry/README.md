# API Registry – Knowledge Store

Single source of truth for API metadata. Two knowledge stores: **in-house** (company APIs) and **external** (third-party/open APIs). Each file is one array of API objects with end-to-end details per API.

## In-house: `api-knowledge-store.json`

Company APIs (Telecom domain): store location, bank check, SIM swap, customer status, top-up, bill pay, usage, money-usage app APIs, etc.

- **Structure:** `{ "_meta": { ... }, "apis": [ ... ] }`
- **Fields per API:** `id`, `name`, `domain`, `description`, `owner`, `team`, `version`, `method`, `path`, `url`, `confluence`, `bitbucket`, `tags`, `sample_input`, `sample_output`, `manhours`, `api_efficiency`, `readiness`

## External: `external-apis-knowledge-store.json`

Commonly used **external / third-party / open APIs**, including:

- **Mapping:** Azure Maps, Google Maps Geocoding, Mapbox, HERE Geocoding, OpenStreetMap Nominatim  
- **Communications:** Twilio (SMS, Voice), SendGrid, Mailgun, Slack, Vonage SMS, Zoom  
- **Payments & finance:** Stripe, PayPal, Plaid  
- **Identity:** Auth0, Firebase Authentication  
- **Reference & testing:** OpenWeatherMap, Exchange Rate API, REST Countries, JSONPlaceholder, Postman Echo, IPinfo, ipify  
- **Productivity & storage:** Microsoft Graph, GitHub API, AWS S3  
- **Content:** Unsplash, News API  

Same schema as in-house (owner = vendor name, team = "Third Party"; `confluence` = docs URL, `bitbucket` = developer portal/signup).

## Teams: `teams.json`

Summary of teams derived from **api-knowledge-store.json**: one object per team with `id`, `name`, `summary`, `what_they_do`, `api_count`, `apis` (list of id + name), `owners`, and `domains`. Use for team-level views and discovery.

## Other files

- **`apis-metadata.json`** – Normalized in-house registry (legacy/reference).
- **`apis-metadata.schema.json`** – JSON Schema for the normalized structure.
