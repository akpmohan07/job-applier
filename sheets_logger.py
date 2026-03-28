import os
from datetime import date

import gspread
from google.oauth2.service_account import Credentials

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_HEADERS = [
    "Date", "Company", "Role", "Location", "Match Score",
    "Recommended CV", "Apply URL", "Contact Email",
    "Should Apply", "Match Reason", "Status",
]


def _get_sheet():
    key_path = os.getenv("GOOGLE_SHEETS_KEY_PATH", "./google_service_account.json")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    creds = Credentials.from_service_account_file(key_path, scopes=_SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id).sheet1


def ensure_headers(sheet):
    first_row = sheet.row_values(1)
    if first_row != _HEADERS:
        sheet.insert_row(_HEADERS, 1)


def log_result(result: dict):
    sheet = _get_sheet()
    ensure_headers(sheet)
    row = [
        str(date.today()),
        result.get("company", ""),
        result.get("role", ""),
        result.get("location", ""),
        result.get("match_score", ""),
        result.get("recommended_cv", ""),
        result.get("apply_url", ""),
        result.get("contact_email", ""),
        str(result.get("should_apply", "")),
        result.get("match_reason", ""),
        "",  # Status — filled manually
    ]
    sheet.append_row(row)


def log_results(results: list[dict]):
    sheet = _get_sheet()
    ensure_headers(sheet)
    rows = []
    for result in results:
        rows.append([
            str(date.today()),
            result.get("company", ""),
            result.get("role", ""),
            result.get("location", ""),
            result.get("match_score", ""),
            result.get("recommended_cv", ""),
            result.get("apply_url", ""),
            result.get("contact_email", ""),
            str(result.get("should_apply", "")),
            result.get("match_reason", ""),
            "",
        ])
    sheet.append_rows(rows)
