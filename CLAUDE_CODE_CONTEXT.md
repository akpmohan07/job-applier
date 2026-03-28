# Job Application Agent — Claude Code Context
> Daytona x Give(a)Go HackSprint Dublin | 28 March 2026

---

## What we are building

A job application research agent. Input is a CSV of job URLs. Parallel Daytona sandboxes scrape each job page, extract structured data, score against a candidate profile, select the best CV, and log everything to Google Sheets. Apply URL is saved in the sheet — user clicks it manually later.

---

## One-line agent task

"Given a CSV of job URLs, spin up parallel Daytona sandboxes to scrape each job, extract key details, score match against candidate profile, pick the right CV, and log everything to Google Sheets."

---

## Final architecture

```
CSV (job URLs)
        ↓
URL parser — read list of job links
        ↓
asyncio.gather — one Daytona sandbox per URL (parallel)
        ↓
Each sandbox:
    - Fixed Python script runs inside sandbox
    - requests.get(url) + BeautifulSoup
    - Returns clean text (first 6000 chars)
        ↓
Host: LLM Call 1 — extract structured job JSON from text
        ↓
Host: LLM Call 2 — score job against candidate profile
        ↓
Host: CV selector — pick best CV from library
        ↓
Host: Google Sheets logger — append row
        ↓
Streamlit UI — show ranked results + link to sheet
```

---

## What runs INSIDE the sandbox (Daytona)

Fixed Python script — same for every job URL:

```python
import requests
from bs4 import BeautifulSoup

url = "{job_url}"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
soup = BeautifulSoup(r.text, "html.parser")

for tag in soup(["script", "style", "nav", "footer", "header"]):
    tag.decompose()

print(soup.get_text(separator="\n", strip=True)[:6000])
```

This is the Daytona justification — running code against unknown/untrusted URLs safely in isolation.

## What runs on HOST (outside sandbox)

- LLM calls (LiteLLM + Groq)
- CV selection logic
- Google Sheets logging
- Streamlit UI

---

## File structure

```
job-agent/
├── .env
├── requirements.txt
├── jobs.csv
├── profile.md
├── cvs/
│   ├── cv_backend_java.pdf
│   ├── cv_fullstack.pdf
│   └── cv_general.pdf
├── main.py
├── orchestrator.py
├── sandboxes/
│   ├── base.py
│   └── job_sandbox.py
├── llm.py
├── cv_selector.py
├── sheets_logger.py
├── prompts/
│   └── prompts.py
└── ui/
    └── app.py
```

---

## .env

```
DAYTONA_API_KEY=your_daytona_key
GROQ_API_KEY=your_groq_key
LITELLM_MODEL_EXTRACT=groq/llama-3.3-70b-versatile
LITELLM_MODEL_SCORE=groq/llama-3.3-70b-versatile
GOOGLE_SHEETS_KEY_PATH=./google_service_account.json
GOOGLE_SHEET_ID=your_sheet_id
```

---

## requirements.txt

```
daytona>=0.153.0
litellm>=1.35.0
gspread>=6.0.0
google-auth>=2.28.0
streamlit>=1.32.0
requests>=2.31.0
beautifulsoup4>=4.12.0
python-dotenv>=1.0.0
```

---

## Input format

```csv
url
https://boards.greenhouse.io/stripe/jobs/123
https://jobs.lever.co/anthropic/456
```

---

## Candidate profile (profile.md)

```markdown
# Candidate — Mohan Muthusamy

## Skills
Java, Spring Boot, Kafka, PostgreSQL, Kubernetes, Docker, Redis, AWS, Python

## Experience
4+ years backend engineering, SaaS products, microservices, Freshworks

## Preferences
Senior roles, backend/full-stack, Dublin or remote, fintech/SaaS/startup
```

---

## LLM prompts

### Call 1 — Extract job details
```
System:
Extract structured information from this job posting text.
Return ONLY valid JSON, no markdown, no backticks, no explanation.
Fields: company, role, location, salary (or null),
required_skills (array), nice_to_have (array),
contact_email (or null), apply_url (or null)

User: {raw_text}
```

### Call 2 — Score + CV selection
```
System:
Score how well the candidate matches this job from 0 to 100.
Return ONLY valid JSON, no markdown, no backticks, no explanation.
Fields: match_score (int), match_reason (string max 100 chars),
recommended_cv (one of: cv_backend_java, cv_fullstack, cv_general),
should_apply (bool)

User:
Candidate: {profile_text}
Job: {job_json}
Available CVs: cv_backend_java, cv_fullstack, cv_general
```

---

## Google Sheets columns

Date | Company | Role | Location | Match Score | Recommended CV | Apply URL | Contact Email | Should Apply | Match Reason | Status

---

## Sandbox lifecycle

- One sandbox per job URL, created fresh per run
- auto_stop_interval=30, auto_delete_interval=60
- Always call sandbox.delete() after getting result
- Use AsyncDaytona + asyncio.gather for parallel execution

---

## Key implementation

### orchestrator.py
```python
async def process_jobs(urls):
    async with AsyncDaytona() as daytona:
        results = await asyncio.gather(*[
            process_single_job(daytona, url) for url in urls
        ])
    return sorted(results, key=lambda x: x.get("match_score", 0), reverse=True)

async def process_single_job(daytona, url):
    sandbox = await daytona.create()
    try:
        raw_text = await job_sandbox.scrape(sandbox, url)
        job_data = llm.extract(raw_text)
        scored = llm.score(job_data)
        return {**job_data, **scored, "url": url}
    finally:
        await sandbox.delete()
```

### sandboxes/job_sandbox.py
```python
async def scrape(sandbox, url):
    code = f"""
import requests
from bs4 import BeautifulSoup
r = requests.get("{url}", headers={{"User-Agent": "Mozilla/5.0"}}, timeout=10)
soup = BeautifulSoup(r.text, "html.parser")
for tag in soup(["script", "style", "nav", "footer"]):
    tag.decompose()
print(soup.get_text(separator="\\n", strip=True)[:6000])
"""
    result = await sandbox.process.code_run(code)
    return result.result
```

---

## Build order

1. sandboxes/job_sandbox.py — scrape one URL, return text
2. llm.py + prompts.py — extract + score
3. orchestrator.py — parallel gather
4. sheets_logger.py — log to Google Sheets
5. ui/app.py — Streamlit UI

First milestone: one URL in → structured JSON out.

---

## Demo script (3 minutes)

1. "Job hunting takes hours of research — we automated it"
2. Upload CSV with 5 job URLs
3. Show sandboxes firing in parallel
4. Show ranked results with match scores
5. Show Google Sheet populated automatically
6. "Apply URL is right there — one click when ready"
7. "v2 adds CV tailoring, v3 adds Computer Use auto-apply"

---

## Why Daytona

Each sandbox scrapes an untrusted unknown URL in isolation. If the site returns malicious content or crashes the script, it affects nothing else. That is the exact use case Daytona is built for — safe execution of code against arbitrary external resources.

---

## Constraints

- No OAuth flows today
- No form filling today — apply URL in sheet, user clicks manually
- Apply step is v2 using Daytona Computer Use
- Keep LLM calls to 2 per job max
- Groq free tier for LLM — no cost

---

*Daytona x Give(a)Go HackSprint Dublin | 28 March 2026*
