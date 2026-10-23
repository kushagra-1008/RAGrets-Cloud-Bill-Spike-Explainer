# RAGrets — Cloud Bill Spike Explainer

RAGrets explains changes between cloud billing periods with deterministic Pandas calculations, provenance records, invoice reconciliation, and a safe, approval-gated action simulation. It starts with synthetic data and requires no paid credentials.

## Setup and launch

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest -q
streamlit run app.py
```

Click **Load synthetic demo**, select `2026-09` and `2026-10`, then review the all-region breakdown. The demo includes a new `ap-south-1` compute resource and `eu-west-1` storage, as well as credits shown separately from usage. Reports export to `reports/` as JSON, CSV, and Markdown.

## Hackathon upload samples

The files in `sample_data/` are fictional and clearly intended for demonstration. Upload [hackathon_billing_demo.json](sample_data/hackathon_billing_demo.json) for the complete flow: it contains four billing records plus September and October invoices, so reconciliation shows the October $270 gross usage, -$10 promotional credit, $0 adjustment, $26 tax, and $286 invoice total. It also demonstrates the newly discovered `ap-south-1` resource at $120 and `eu-west-1` storage at $50.

[hackathon_billing_demo.csv](sample_data/hackathon_billing_demo.csv) contains the same billing-detail rows in the exact CSV schema accepted by the uploader. The current CSV loader does not support invoice records, so it is appropriate for cost-breakdown demos but will show missing-invoice warnings rather than reconciliation. Use the JSON sample for the complete hackathon walkthrough.

## Architecture

- `schemas.py`: Pydantic validation for billing, invoice, evidence, and actions.
- `database.py`: SQLite normalized payloads, ingestion runs, evidence, idempotently saved reports and action results, approvals, and audit events.
- `ingestion/`: synthetic, CSV/JSON, PDF evidence candidates, and consented HTTP dashboard access.
- `analysis/`: deterministic period comparisons and reconciliation with a `$0.01` tolerance.
- `workflow.py`: LangGraph sequencing of validation, reconciliation, analysis, and reporting.
- `approvals.py`: idempotent approval and simulated execution. No cloud provider executor is implemented.
- `app.py`: Streamlit dashboard and report download.

## Input format

CSV exports contain the billing fields in `BillingRecord` (account, `billing_period` as `YYYY-MM`, service, region, resource ID, usage, price, gross usage cost, credits, adjustments, net cost, and source record ID). JSON accepts either a list of records or `{ "records": [...], "invoices": [...] }`. Credits conventionally use negative values. PDF parsing records page/amount candidates as evidence only, because uncertain extraction is never silently accepted.

## Optional Groq AI features

The deterministic calculations run only when the user asks the first chat question. To enable live AI chat, set `RAGRETS_GROQ_API_KEY` and optionally `RAGRETS_GROQ_MODEL` (default: `openai/gpt-oss-20b`) in the process environment before starting Streamlit. Upload a billing export, then write a question. The agent reads the uploaded billing data with read-only tools and answers from its analysis; no dashboard metrics, tables, or pre-generated investigation are shown. The temporary chat history lives in the Streamlit session and clears when the source file changes, the bill is reset, or the user clears chat. When you submit a question, report aggregates, recent chat turns, and any billing rows requested by the agent may be sent to Groq. Raw file bytes are not uploaded. AI explanations are separate from deterministic calculations. Provider errors are shown in the chat; no offline text is presented as an AI result.

For local setup, copy `.env.example` to `.env` and load the values into your shell with your preferred environment-variable tool. `.env` is ignored by Git. Never commit credentials. The app does not read `.env` automatically.

## Safety and limitations

Dashboard access is explicit and does not bypass authentication, OTPs, CAPTCHAs, or access controls. All “delete” flows are simulated and require a second approval; the audit trail states that no real resource was changed. Voice output is unavailable because no speech provider is configured. LangGraph orchestrates the workflow while calculations remain ordinary deterministic Python.
# RAGrets-Cloud-Bill-Spike-Explainer
