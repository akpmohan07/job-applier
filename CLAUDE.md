# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A job application research agent built for the Daytona x Give(a)Go HackSprint Dublin. Given a CSV of job URLs, it spins up parallel Daytona sandboxes to scrape each job page, extracts structured data via LLM, scores match against a candidate profile, picks the best CV, and logs results to Google Sheets. A Streamlit UI shows ranked results.

## Running the Project

```bash
# Install dependencies
pip install -r requirements.txt

# Run the main orchestrator
python main.py

# Run the Streamlit UI
streamlit run ui/app.py
```

## Environment Setup

Create a `.env` file with:

```
DAYTONA_API_KEY=your_daytona_key
GROQ_API_KEY=your_groq_key
LITELLM_MODEL_EXTRACT=groq/llama-3.3-70b-versatile
LITELLM_MODEL_SCORE=groq/llama-3.3-70b-versatile
GOOGLE_SHEETS_KEY_PATH=./google_service_account.json
GOOGLE_SHEET_ID=your_sheet_id
```

Also requires `google_service_account.json` (not committed) and `profile.md` with candidate details.

## Architecture

**Data flow:**
1. `main.py` reads `jobs.csv` (single `url` column)
2. `orchestrator.py` runs one Daytona sandbox per URL in parallel via `asyncio.gather`
3. Each sandbox (`sandboxes/job_sandbox.py`) executes a fixed scraping script inside an isolated Daytona environment using `sandbox.process.code_run()`
4. **Back on host:** `llm.py` makes 2 sequential Groq calls per job — first to extract structured JSON, then to score match against `profile.md`
5. `sheets_logger.py` appends a row to Google Sheets
6. `ui/app.py` (Streamlit) displays ranked results

**Critical architecture point:** Web scraping runs *inside* Daytona sandboxes (untrusted URLs in isolation). All LLM calls, CV selection, and Sheets logging run on the host. Sandbox lifecycle: `auto_stop_interval=30`, `auto_delete_interval=60`, always `await sandbox.delete()` in a `finally` block.

## Key Implementation Details

**LLM calls** use LiteLLM (`groq/llama-3.3-70b-versatile`) and must return raw JSON — no markdown, no backticks:
- Call 1 (extract): fields `company, role, location, salary, required_skills, nice_to_have, contact_email, apply_url`
- Call 2 (score): fields `match_score (0-100), match_reason (≤100 chars), recommended_cv (cv_backend_java|cv_fullstack|cv_general), should_apply (bool)`

**Google Sheets columns:** `Date | Company | Role | Location | Match Score | Recommended CV | Apply URL | Contact Email | Should Apply | Match Reason | Status`

**CV library** lives in `cvs/`: `cv_backend_java.pdf`, `cv_fullstack.pdf`, `cv_general.pdf`

## Build Order

Build in this sequence — each step depends on the previous:
1. `sandboxes/job_sandbox.py` — scrape one URL, return text
2. `llm.py` + `prompts/prompts.py` — extract + score
3. `orchestrator.py` — parallel gather
4. `sheets_logger.py` — Google Sheets logging
5. `ui/app.py` — Streamlit UI

First milestone: one URL in → structured JSON out.

## Constraints

- No OAuth flows — uses service account for Google Sheets
- No form filling — apply URL is logged to sheet, user clicks manually
- Max 2 LLM calls per job (Groq free tier)
- Computer Use auto-apply is out of scope (planned v3)
