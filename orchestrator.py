import asyncio
import json
import logging
from daytona import AsyncDaytona, CreateSandboxFromSnapshotParams

import llm
from sandboxes import job_sandbox

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


async def process_single_job(daytona, url: str, profile_text: str) -> dict:
    short_url = url.split("?")[0]
    log.info(f"[SANDBOX] Creating sandbox for: {short_url}")
    sandbox = await daytona.create(
        CreateSandboxFromSnapshotParams(
            auto_stop_interval=30,
            auto_delete_interval=60,
        )
    )
    log.info(f"[SANDBOX] Ready (id={sandbox.id}) — scraping: {short_url}")
    try:
        raw = await job_sandbox.scrape(sandbox, url)
        log.info(f"[SCRAPE]  Done for: {short_url}")

        if "linkedin.com/jobs" in url:
            job_data = json.loads(raw)
            log.info(f"[PARSE]   LinkedIn structured data: {job_data.get('role')} @ {job_data.get('company')}")
        else:
            log.info(f"[LLM]     Extracting job details for: {short_url}")
            job_data = llm.extract(raw)
            log.info(f"[LLM]     Extracted: {job_data.get('role')} @ {job_data.get('company')}")

        log.info(f"[LLM]     Scoring match for: {job_data.get('role')} @ {job_data.get('company')}")
        scored = llm.score(job_data, profile_text)
        log.info(f"[SCORE]   {job_data.get('company')} — score={scored.get('match_score')} should_apply={scored.get('should_apply')}")

        return {"url": url, **job_data, **scored}
    except Exception as e:
        log.error(f"[ERROR]   {short_url}: {e}")
        return {"url": url, "error": str(e), "match_score": 0}
    finally:
        try:
            await sandbox.delete()
            log.info(f"[SANDBOX] Deleted (id={sandbox.id})")
        except Exception:
            pass  # sandbox auto-deletes via auto_delete_interval


async def process_jobs(urls: list[str], profile_text: str) -> list[dict]:
    log.info(f"Launching {len(urls)} sandbox(es) in parallel...")
    async with AsyncDaytona() as daytona:
        results = await asyncio.gather(
            *[process_single_job(daytona, url, profile_text) for url in urls]
        )
    log.info("All sandboxes complete. Ranking results...")
    return sorted(results, key=lambda x: x.get("match_score", 0), reverse=True)
