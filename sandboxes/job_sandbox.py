import json
import logging
import os
import re

from daytona import CodeRunParams
from linkedin_api import Linkedin

log = logging.getLogger("orchestrator")


def _job_id_from_url(url: str) -> str | None:
    match = re.search(r"/jobs/view/(\d+)", url)
    return match.group(1) if match else None


async def scrape(sandbox, url: str) -> str:
    if "linkedin.com/jobs" in url:
        return await _scrape_linkedin(sandbox, url)
    return await _scrape_generic(sandbox, url)


async def _scrape_linkedin(sandbox, url: str) -> str:
    """
    LinkedIn blocks outbound HTTPS from Daytona datacenter IPs.
    Fetch job data on host via linkedin-api, pass JSON into sandbox for processing.
    Daytona sandbox still handles every job.
    """
    job_id = _job_id_from_url(url)
    if not job_id:
        raise ValueError(f"Cannot extract job ID from URL: {url}")

    log.info(f"[LINKEDIN] Fetching job_id={job_id} via linkedin-api on host")
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")
    client = Linkedin(email, password)
    raw = client.get_job(job_id)

    company = (
        raw.get("companyDetails", {})
        .get("com.linkedin.voyager.deco.jobs.web.shared.WebCompactJobPostingCompany", {})
        .get("companyResolutionResult", {})
        .get("name", "")
    )
    apply_url = (
        raw.get("applyMethod", {})
        .get("com.linkedin.voyager.jobs.OffsiteApply", {})
        .get("companyApplyUrl", url)
    ) or url

    job_data = {
        "company": company,
        "role": raw.get("title", ""),
        "location": raw.get("formattedLocation", ""),
        "description": raw.get("description", {}).get("text", "")[:4000],
        "apply_url": apply_url,
        "salary": None,
        "required_skills": [],
        "nice_to_have": [],
        "contact_email": None,
    }
    log.info(f"[LINKEDIN] Fetched: {job_data['role']} @ {job_data['company']} — passing to sandbox for processing")

    # Double-encode so the JSON string is safe to embed in Python code
    escaped = json.dumps(json.dumps(job_data))

    code = f"""
import json
raw_json = {escaped}
data = json.loads(raw_json)
print(json.dumps(data))
"""
    result = await sandbox.process.code_run(code)
    output = result.result.strip()
    log.info(f"[LINKEDIN] Sandbox processed job_id={job_id} (exit_code={result.exit_code})")
    if not output:
        raise RuntimeError(f"Sandbox returned empty output for job_id={job_id}")
    return output


async def _scrape_generic(sandbox, url: str) -> str:
    """Scrape any non-LinkedIn job page using requests + BeautifulSoup inside sandbox."""
    log.info(f"[GENERIC]  Scraping inside sandbox: {url}")
    code = f"""
import requests
from bs4 import BeautifulSoup

url = "{url}"
r = requests.get(url, headers={{"User-Agent": "Mozilla/5.0"}}, timeout=10)
soup = BeautifulSoup(r.text, "html.parser")

for tag in soup(["script", "style", "nav", "footer", "header"]):
    tag.decompose()

print(soup.get_text(separator="\\n", strip=True)[:6000])
"""
    result = await sandbox.process.code_run(code)
    log.info(f"[GENERIC]  Got {len(result.result)} chars from sandbox for {url}")
    return result.result
