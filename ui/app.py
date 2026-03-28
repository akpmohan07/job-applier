import asyncio
import csv
import io
import logging
import queue
import sys
import threading
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

import orchestrator
import sheets_logger

st.set_page_config(page_title="Job Applier", page_icon="💼", layout="wide")
st.title("💼 Job Application Agent")

# --- Sidebar ---
st.sidebar.header("Input")
uploaded = st.sidebar.file_uploader("Upload jobs.csv", type="csv")
use_default = st.sidebar.checkbox("Use jobs.csv from project root", value=True)
run_btn = st.sidebar.button("Run Agent", type="primary")


class _QueueHandler(logging.Handler):
    """Logging handler that pushes records into a queue for Streamlit to consume."""
    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q

    def emit(self, record):
        self.q.put(self.format(record))


if run_btn:
    if uploaded:
        content = uploaded.read().decode()
        reader = csv.DictReader(io.StringIO(content))
        urls = [row["url"].strip() for row in reader if row.get("url", "").strip()]
    elif use_default and Path("jobs.csv").exists():
        with open("jobs.csv", newline="") as f:
            urls = [row["url"].strip() for row in csv.DictReader(f) if row["url"].strip()]
    else:
        st.error("No input provided.")
        st.stop()

    if not urls:
        st.warning("No URLs found in CSV.")
        st.stop()

    profile_text = Path("profile.md").read_text() if Path("profile.md").exists() else ""

    st.subheader(f"Running {len(urls)} job(s) in parallel Daytona sandboxes...")

    # Live log panel
    log_container = st.container(border=True)
    log_placeholder = log_container.empty()
    log_lines: list[str] = []

    # Wire up logging → queue → Streamlit
    log_queue: queue.Queue = queue.Queue()
    handler = _QueueHandler(log_queue)
    handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
    orch_logger = logging.getLogger("orchestrator")
    orch_logger.addHandler(handler)

    results_holder: dict = {}
    error_holder: dict = {}

    def _run():
        try:
            results_holder["data"] = asyncio.run(
                orchestrator.process_jobs(urls, profile_text)
            )
        except Exception as e:
            error_holder["err"] = e

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    # Poll queue and update log panel while thread is running
    while thread.is_alive() or not log_queue.empty():
        while not log_queue.empty():
            log_lines.append(log_queue.get_nowait())
            log_placeholder.code("\n".join(log_lines[-30:]), language=None)
        thread.join(timeout=0.3)

    orch_logger.removeHandler(handler)

    if "err" in error_holder:
        st.error(f"Agent failed: {error_holder['err']}")
        st.stop()

    results = results_holder.get("data", [])

    # Log to Sheets
    try:
        sheets_logger.log_results(results)
        st.success("Results logged to Google Sheets.")
    except Exception as e:
        st.warning(f"Sheets logging failed: {e}")

    # Display results
    st.subheader(f"Results — {len(results)} job(s) ranked by match score")

    for r in results:
        score = r.get("match_score", 0)
        company = r.get("company", "Unknown")
        role = r.get("role", "Unknown")
        color = "green" if score >= 70 else "orange" if score >= 40 else "red"

        with st.expander(f":{color}[{score}] {company} — {role}", expanded=score >= 70):
            if "error" in r:
                st.error(r["error"])
                st.caption(r["url"])
                continue

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Match Score", score)
                st.write(f"**Location:** {r.get('location', 'N/A')}")
                st.write(f"**Salary:** {r.get('salary', 'N/A')}")
                st.write(f"**Recommended CV:** `{r.get('recommended_cv', 'N/A')}`")
                st.write(f"**Should Apply:** {'✅' if r.get('should_apply') else '❌'}")
            with col2:
                st.write(f"**Match Reason:** {r.get('match_reason', '')}")
                if r.get("apply_url"):
                    st.link_button("Apply →", r["apply_url"])
                if r.get("required_skills"):
                    st.write(f"**Required:** {', '.join(r['required_skills'])}")
                if r.get("nice_to_have"):
                    st.write(f"**Nice to have:** {', '.join(r['nice_to_have'])}")

else:
    st.info("Upload a CSV of job URLs and click **Run Agent** to start.")
    st.markdown("""
**Expected CSV format:**
```
url
https://www.linkedin.com/jobs/view/4392733592
https://boards.greenhouse.io/company/jobs/123
```
""")
