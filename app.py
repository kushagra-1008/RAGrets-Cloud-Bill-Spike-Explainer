import tempfile
import json
from pathlib import Path
import streamlit as st
from ragrets.database import Database
from ragrets.ingestion import demo_data, ingest_file, ingest_records
from ragrets.workflow import run_workflow
from ragrets.reporting import ready_for_new_bill_message
from ragrets.config import Settings
from ragrets.groq import GroqAPIError, GroqClient

st.set_page_config(page_title="RAGrets", page_icon="📉", layout="wide")
st.title("RAGrets — Cloud Bill Spike Explainer")
st.caption("Deterministic calculations with traceable source evidence. Demo mode never changes cloud resources.")
db = Database("ragrets.db")
st.session_state.setdefault("reset_confirmation_pending", False)
st.session_state.setdefault("billing_upload_generation", 0)
st.session_state.setdefault("reset_message", None)


def request_reset():
    st.session_state["reset_confirmation_pending"] = True


def cancel_reset():
    st.session_state["reset_confirmation_pending"] = False


def confirm_reset():
    db.clear_billing_data()
    st.session_state["reset_confirmation_pending"] = False
    st.session_state["billing_upload_generation"] += 1
    st.session_state.pop("selected_account", None)
    st.session_state.pop("comparison_previous", None)
    st.session_state.pop("comparison_current", None)
    st.session_state.pop("ragrets_chat_context", None)
    st.session_state.pop("ragrets_chat_history", None)
    st.session_state["reset_message"] = "Ready for a new billing file. Upload CSV or JSON to begin."


with st.sidebar:
    st.header("Data source")
    st.button("Reset / New Bill", on_click=request_reset, width="stretch")
    if st.session_state["reset_confirmation_pending"]:
        st.warning("Clear the currently loaded billing records, invoices, and evidence? Approval and audit history will be preserved.", title="Confirm reset")
        confirm, cancel = st.columns(2)
        confirm.button("Confirm reset", on_click=confirm_reset, width="stretch")
        cancel.button("Cancel", on_click=cancel_reset, width="stretch")
    upload = st.file_uploader(
        "CSV or JSON billing export",
        type=["csv", "json"],
        key=f"billing_upload_{st.session_state['billing_upload_generation']}",
    )
    if st.button("Load synthetic demo"):
        records, invoices = demo_data(); ingest_records(db, records, invoices, "synthetic-demo"); st.success("Demo data loaded")
    if upload:
        suffix = Path(upload.name).suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(upload.getvalue()); temp_path = handle.name
        result = ingest_file(db, temp_path, upload.name)
        (st.success if result["status"] == "completed" else st.error)(str(result))

records, invoices, evidence = db.records(), db.invoices(), db.evidence()
ready_message = ready_for_new_bill_message(records, st.session_state["reset_message"])
if ready_message:
    if st.session_state["reset_message"]:
        st.success(ready_message)
    else:
        st.info(ready_message)
    st.stop()
st.subheader("RAGrets billing chat")
settings = Settings()
groq = GroqClient(settings.groq_api_key, settings.groq_model)
if not groq.configured:
    st.info("The billing agent is unavailable until RAGRETS_GROQ_API_KEY is configured.")
else:
    accounts = sorted({record.account for record in records})
    chat_context = json.dumps({
        "accounts": accounts,
        "sources": sorted((item.source_id, item.content_hash) for item in evidence),
    })
    if st.session_state.get("ragrets_chat_context") != chat_context:
        st.session_state["ragrets_chat_context"] = chat_context
        st.session_state["ragrets_chat_history"] = []
    chat_history = st.session_state["ragrets_chat_history"]
    chat_title, chat_clear = st.columns([5, 1])
    chat_title.caption("Your billing file is ready. Ask a question to start the analysis.")
    if chat_clear.button("Clear chat", key="clear_ragrets_chat"):
        st.session_state["ragrets_chat_history"] = []
        st.rerun()
    st.caption("Chat history is temporary to this browser session and comparison. It is cleared when you change the account or periods, reset the bill, or select Clear chat.")
    for message in chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    question = st.chat_input("Write your question here")
    if question:
        history = st.session_state["ragrets_chat_history"]
        history.append({"role": "user", "content": question})
        try:
            account = accounts[0]
            account_records = [record for record in records if record.account == account]
            account_invoices = [invoice for invoice in invoices if invoice.account == account]
            periods = sorted({record.billing_period for record in account_records})
            if len(periods) < 2:
                raise ValueError("The uploaded billing file needs at least two billing periods before I can compare costs.")
            state = run_workflow(
                account,
                periods[-2],
                periods[-1],
                records,
                invoices,
                evidence,
            )
            if state.get("errors"):
                raise ValueError("; ".join(state["errors"]))
            report = state["report"]
            db.save_report(report, account, periods[-2], periods[-1])
            answer = groq.answer_question(report, question, history[:-1], account_records, account_invoices)
            history.append({"role": "assistant", "content": answer})
            del history[:-20]
        except (GroqAPIError, ValueError) as exc:
            st.error(str(exc))
        with st.chat_message("user"):
            st.markdown(question)
        if history and history[-1]["role"] == "assistant":
            with st.chat_message("assistant"):
                st.markdown(history[-1]["content"])
