EXTRACT_SYSTEM = """Extract structured information from this job posting text.
Return ONLY valid JSON, no markdown, no backticks, no explanation.
Fields: company, role, location, salary (or null),
required_skills (array), nice_to_have (array),
contact_email (or null), apply_url (or null)"""

SCORE_SYSTEM = """Score how well the candidate matches this job from 0 to 100.
Return ONLY valid JSON, no markdown, no backticks, no explanation.
Fields: match_score (int), match_reason (string max 100 chars),
recommended_cv (one of: cv_backend_java, cv_fullstack, cv_general),
should_apply (bool)"""
