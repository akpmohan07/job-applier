import asyncio
import csv
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import orchestrator
import sheets_logger


def read_urls(csv_path: str = "jobs.csv") -> list[str]:
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        return [row["url"].strip() for row in reader if row["url"].strip()]


def read_profile(profile_path: str = "profile.md") -> str:
    return Path(profile_path).read_text()


async def main():
    urls = read_urls()
    if not urls:
        print("No URLs found in jobs.csv")
        return

    print(f"Processing {len(urls)} job(s)...")
    profile_text = read_profile()
    results = await orchestrator.process_jobs(urls, profile_text)

    print(f"\nResults (ranked by match score):")
    for r in results:
        if "error" in r:
            print(f"  [ERROR] {r['url']}: {r['error']}")
        else:
            print(f"  [{r.get('match_score', '?'):>3}] {r.get('company', '?')} — {r.get('role', '?')}")

    print("\nLogging to Google Sheets...")
    sheets_logger.log_results(results)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
