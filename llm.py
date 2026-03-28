import json
import os
import litellm
from prompts.prompts import EXTRACT_SYSTEM, SCORE_SYSTEM

_MODEL_EXTRACT = os.getenv("LITELLM_MODEL_EXTRACT", "groq/llama-3.3-70b-versatile")
_MODEL_SCORE = os.getenv("LITELLM_MODEL_SCORE", "groq/llama-3.3-70b-versatile")


def _call(model: str, system: str, user: str) -> dict:
    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    raw = response.choices[0].message.content.strip()
    return json.loads(raw)


def extract(raw_text: str) -> dict:
    """Call 1: extract structured job data from scraped page text."""
    return _call(_MODEL_EXTRACT, EXTRACT_SYSTEM, raw_text)


def score(job_data: dict, profile_text: str) -> dict:
    """Call 2: score job match against candidate profile."""
    user = (
        f"Candidate: {profile_text}\n"
        f"Job: {json.dumps(job_data)}\n"
        f"Available CVs: cv_backend_java, cv_fullstack, cv_general"
    )
    return _call(_MODEL_SCORE, SCORE_SYSTEM, user)
