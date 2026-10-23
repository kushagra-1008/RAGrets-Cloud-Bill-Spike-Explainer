import hashlib
import json
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL
import pandas as pd
from pydantic import ValidationError
from ..database import Database
from ..schemas import BillingRecord, InvoiceRecord, EvidenceRecord


RECORD_COLUMNS = set(BillingRecord.model_fields) - {"source_id"}
INVOICE_COLUMNS = set(InvoiceRecord.model_fields) - {"source_id"}


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def ingest_records(db: Database, records_data: list[dict], invoices_data: list[dict], source_id: str, raw: bytes | None = None) -> dict:
    raw = raw or json.dumps({"records": records_data, "invoices": invoices_data}, sort_keys=True).encode()
    content_hash = _digest(raw)
    run_id = str(uuid5(NAMESPACE_URL, content_hash))
    issues = []
    try:
        records = [BillingRecord(**item, source_id=source_id) for item in records_data]
        invoices = [InvoiceRecord(**item, source_id=source_id) for item in invoices_data]
    except ValidationError as exc:
        issues.append(str(exc))
        db.record_run(run_id, content_hash, "failed", issues)
        return {"run_id": run_id, "status": "failed", "issues": issues}
    db.record_run(run_id, content_hash, "completed")
    db.save_records(records)
    db.save_invoices(invoices)
    db.save_evidence(EvidenceRecord(source_id=source_id, content_hash=content_hash, reference="normalized billing export"))
    return {"run_id": run_id, "status": "completed", "records": len(records), "invoices": len(invoices), "issues": issues}


def ingest_file(db: Database, path: str | Path, source_id: str | None = None) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    source_id = source_id or path.name
    if path.suffix.lower() == ".csv":
        records = pd.read_csv(path).fillna(0).to_dict("records")
        return ingest_records(db, records, [], source_id, raw)
    if path.suffix.lower() == ".json":
        payload = json.loads(raw)
        if isinstance(payload, list):
            payload = {"records": payload, "invoices": []}
        return ingest_records(db, payload.get("records", []), payload.get("invoices", []), source_id, raw)
    raise ValueError("Only CSV and JSON billing exports are supported by this loader")


def demo_data():
    records = [
        {"account":"demo-acct","billing_period":"2026-09","service":"Compute","region":"us-east-1","resource_id":"i-steady","usage_quantity":100,"usage_unit":"hours","unit_price":1,"usage_cost":100,"credits":-10,"adjustments":0,"net_cost":90,"source_record_id":"sep-1"},
        {"account":"demo-acct","billing_period":"2026-10","service":"Compute","region":"us-east-1","resource_id":"i-steady","usage_quantity":100,"usage_unit":"hours","unit_price":1,"usage_cost":100,"credits":-10,"adjustments":0,"net_cost":90,"source_record_id":"oct-1"},
        {"account":"demo-acct","billing_period":"2026-10","service":"Compute","region":"ap-south-1","resource_id":"i-new","usage_quantity":80,"usage_unit":"hours","unit_price":1.5,"usage_cost":120,"credits":0,"adjustments":0,"net_cost":120,"source_record_id":"oct-2"},
        {"account":"demo-acct","billing_period":"2026-10","service":"Storage","region":"eu-west-1","resource_id":"bucket-logs","usage_quantity":1000,"usage_unit":"GB-month","unit_price":0.05,"usage_cost":50,"credits":0,"adjustments":0,"net_cost":50,"source_record_id":"oct-3"},
    ]
    invoices = [
        {"account":"demo-acct","billing_period":"2026-09","usage_subtotal":100,"credits":-10,"adjustments":0,"tax":9,"invoice_total":99},
        {"account":"demo-acct","billing_period":"2026-10","usage_subtotal":270,"credits":-10,"adjustments":0,"tax":26,"invoice_total":286},
    ]
    return records, invoices
