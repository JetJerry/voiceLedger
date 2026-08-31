VoiceLedger — AI-first Merchant Assistant
=========================================

Last updated: 2026-08-31T22:09:02+05:30

Table of contents
-----------------
- Project overview
- Key features (what's implemented)
- High-level architecture
- Quick start (development)
- Environment variables and configuration
- Important files and where to look
- API highlights and examples
- LLM provider configuration
- Razorpay webhook notes
- Admin & management tools
- Tests
- Observability & logging
- Contributing guide and next steps
- License

Project overview
----------------
VoiceLedger is an AI-first assistant for small and local merchants. It empowers shopkeepers to record sales, manage a product catalog, check payment status, and interact with the system using Hindi, Hinglish, or English spoken commands. The backend is a FastAPI service with a small SQLAlchemy-based persistence layer and a pluggable LLM abstraction for intent extraction and contextual answers.

Key features (what's implemented)
---------------------------------
- LLM provider abstraction supporting Gemini, OpenAI, and a Mock provider (provider/adapter pattern).
- Robust rule-based fallback engine for intent extraction (Hindi/Hinglish-first heuristics).
- Hardened Razorpay webhook verification and idempotency handling.
- Merchant onboarding and dynamic product catalog endpoints.
- Persistent merchant business profile (JSON) with GET/POST and admin import/export hooks.
- Basic structured logging and request-level middleware for observability.
- CLI utility to export/import merchant profiles for backups and migration.

High-level architecture
-----------------------
- FastAPI backend: backend/app/main.py
- DB layer: SQLAlchemy models and session (backend/app/db)
- LLM service: backend/app/services/llm_service.py (provider adapters and safe fallbacks)
- Sales & catalog domain services: backend/app/services/sales_service.py
- Webhook handling: backend/app/api/webhooks.py / backend/app/services/razorpay_service.py
- Agents for orchestrating voice flows: backend/app/agents/merchant_agent.py
- Merchant profile persistence: backend/app/models/merchant_profile.py

Quick start (development)
-------------------------
Prerequisites:
- Python 3.10+ (project tests were developed against a modern 3.10+ runtime)
- Git
- (Optional) Virtual environment tool (venv)

1. Clone repository

   git clone <repo-url> D:/razorpay
   cd D:/razorpay

2. Create and activate a venv (recommended)

   python -m venv .venv
   .\.venv\Scripts\activate

3. Install dependencies

   pip install -r backend/requirements.txt

4. Configure environment variables (see below for list)
   - The app reads configuration from backend/app/config.py via pydantic settings.
   - A simple .env file in the repo root or environment variables are acceptable.

5. Run database initialization (if provided) or ensure DB is accessible
   - The project uses settings.DATABASE_URL (default is usually sqlite for dev).

6. Start the dev server

   uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

7. Open API docs

   Visit http://127.0.0.1:8000/docs for OpenAPI UI (when server is running).

Environment variables and configuration
---------------------------------------
Below are the most relevant configuration keys (defined in backend/app/config.py). Set them securely in your environment or .env:

- DATABASE_URL: SQLAlchemy URL (e.g. sqlite:///voiceledger.db or postgresql://user:pw@host/db)
- DEBUG: set to true for local/dev convenience (permissive webhook behavior)
- LOG_LEVEL: logging level (INFO, DEBUG, WARNING, ERROR)
- LOG_FORMAT: optional format config
- LLM_PROVIDER: one of "gemini", "openai", or "mock" (default: gemini)
- GEMINI_API_KEY: API key for Gemini (if using provider)
- OPENAI_API_KEY: API key for OpenAI (if using provider)
- LLM_MODEL: default LLM model name used by providers
- LLM_REQUEST_TIMEOUT_SECONDS: request timeout for remote LLM calls
- RAZORPAY_WEBHOOK_SECRET: secret used to verify Razorpay webhooks

Important files (where to look)
-------------------------------
- App bootstrap & middleware:
  - [backend/app/main.py](D:/razorpay/backend/app/main.py)

- Config & settings:
  - [backend/app/config.py](D:/razorpay/backend/app/config.py)

- LLM service & providers:
  - [backend/app/services/llm_service.py](D:/razorpay/backend/app/services/llm_service.py)

- Razorpay integration & webhook handling:
  - [backend/app/services/razorpay_service.py](D:/razorpay/backend/app/services/razorpay_service.py)
  - [backend/app/api/webhooks.py](D:/razorpay/backend/app/api/webhooks.py)

- Merchant profile model & API:
  - [backend/app/models/merchant_profile.py](D:/razorpay/backend/app/models/merchant_profile.py)
  - [backend/app/api/sales.py](D:/razorpay/backend/app/api/sales.py) (catalog and profile endpoints)

- Agents (orchestration):
  - [backend/app/agents/merchant_agent.py](D:/razorpay/backend/app/agents/merchant_agent.py)

- Tests:
  - [backend/tests/] (see test files for examples and expectations)

- Admin tooling:
  - CLI manage tool: [backend/tools/manage_profiles.py](D:/razorpay/backend/tools/manage_profiles.py)

API highlights and examples
---------------------------
The service exposes endpoints under /sales for catalog and merchant operations. Key endpoints:

- GET /sales/catalog/merchant
  - Returns the currently active merchant catalog context.

- POST /sales/catalog/merchant
  - Create or activate a merchant (onboarding).

- GET /sales/catalog/merchant/profile
  - Return the stored merchant business profile (JSON) or an empty structure if none exists.

- POST /sales/catalog/merchant/profile
  - Upsert the merchant profile JSON (used by UI and as LLM context).

- POST /sales/catalog/merchant/profile/preview
  - LLM-driven preview/validation: accepts a profile JSON and returns a suggested modules list and short summary. Useful for frontend preview before persisting.

- Admin export/import:
  - GET /sales/admin/merchant/{merchant_id}/profile/export
  - POST /sales/admin/merchant/{merchant_id}/profile/import

Example: upsert profile

curl -X POST "http://127.0.0.1:8000/sales/catalog/merchant/profile" \
  -H "Content-Type: application/json" \
  -d '{"config": {"currency": "INR", "products": [{"name": "chai", "price": 20}]}}'

Example: profile preview

curl -X POST "http://127.0.0.1:8000/sales/catalog/merchant/profile/preview" \
  -H "Content-Type: application/json" \
  -d '{"config": {"currency": "INR", "products": [{"name": "chai", "price": 20}]}}'

LLM provider configuration
--------------------------
To minimize coupling to one provider, the project uses a provider abstraction in:

- [backend/app/services/llm_service.py](D:/razorpay/backend/app/services/llm_service.py)

Set LLM_PROVIDER to select one of the adapters:
- gemini — uses the Google GenAI client (if configured)
- openai — uses OpenAI responses API (if configured)
- mock — deterministic, local mock provider (useful for testing)

Provider-specific API keys are read from GEMINI_API_KEY and OPENAI_API_KEY. The code includes the ability to summarize merchant profiles (summarize_profile) so only compact contextual information is injected into LLM prompts when appropriate.

Razorpay webhook notes
----------------------
- Razorpay webhook ingestion is located at [backend/app/api/webhooks.py](D:/razorpay/backend/app/api/webhooks.py) and verification in [backend/app/services/razorpay_service.py](D:/razorpay/backend/app/services/razorpay_service.py).
- Important guidance:
  - Set RAZORPAY_WEBHOOK_SECRET in production to enable strict signature verification.
  - In debug mode (DEBUG=true), the service is permissive to allow local testing; however, keep secrets configured for any external-facing environment.
  - Webhook handling includes simple idempotency checks and robust error logging — monitor the logs for failed reconciliations.

Admin & management tools
------------------------
A small CLI convenience script is included to export/import merchant profiles to JSON for backups or migration:

- [backend/tools/manage_profiles.py](D:/razorpay/backend/tools/manage_profiles.py)

Usage examples:

- Export profile to file
  python backend/tools/manage_profiles.py export --merchant-id 1 --out profile.json

- Import profile from file
  python backend/tools/manage_profiles.py import --merchant-id 1 --in profile.json

Tests
-----
Run the existing test suite (pytest) from the repository root:

pip install -r backend/requirements.txt
pytest -q backend/tests

The test suite exercises webhook handling, onboarding flows, profile endpoints, and the LLM mock provider for deterministic tests.

Observability & logging
-----------------------
- Structured logging and request middleware are implemented in [backend/app/main.py](D:/razorpay/backend/app/main.py). Configure LOG_LEVEL and LOG_FORMAT in env to control verbosity and format.
- For production observability, integrate Sentry or OpenTelemetry (hooks were planned; adjust settings and add instrumentation as needed).

Contributing guide and next steps
---------------------------------
If you want to contribute, please follow these guidelines:
- Create a feature branch using the convention feature/<short-desc>.
- Run tests locally and keep changes small & focused.
- Add unit tests for new behavior (especially when changing extraction logic).

Suggested next work items (already tracked in the project todos):
- Improve voice extraction accuracy (LLM prompt tuning and optional STT integration).
- Add end-to-end tests simulating a full sale -> payment link -> webhook flow.
- Dockerize the dev environment and add docker-compose for local testing.
- Protect admin endpoints (API key or RBAC) before exposing in staging/production.

License
-------
This repository does not currently include a formal license file. If this repository will be shared, add a LICENSE file (e.g., MIT) and update this README accordingly.

Contact & acknowledgements
--------------------------
VoiceLedger is an evolving project. For questions about architecture, LLM prompts, or running the code locally, open an issue or reach out to the maintainers.


Appendix — quick links
----------------------
- App bootstrap: [backend/app/main.py](D:/razorpay/backend/app/main.py)
- LLM service: [backend/app/services/llm_service.py](D:/razorpay/backend/app/services/llm_service.py)
- Merchant profile model: [backend/app/models/merchant_profile.py](D:/razorpay/backend/app/models/merchant_profile.py)
- Sales & profile endpoints: [backend/app/api/sales.py](D:/razorpay/backend/app/api/sales.py)
- Webhooks: [backend/app/api/webhooks.py](D:/razorpay/backend/app/api/webhooks.py)
- Razorpay service: [backend/app/services/razorpay_service.py](D:/razorpay/backend/app/services/razorpay_service.py)
- Agent orchestration: [backend/app/agents/merchant_agent.py](D:/razorpay/backend/app/agents/merchant_agent.py)
- Admin CLI: [backend/tools/manage_profiles.py](D:/razorpay/backend/tools/manage_profiles.py)

Thank you for using and improving VoiceLedger.
