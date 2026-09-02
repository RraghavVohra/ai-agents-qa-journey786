"""
fetcher.py -- pulls Delhi PM2.5 data from OpenAQ, saves as CSV

This is the entry point into the whole agent pipeline -- everything
downstream (Profiler, Explorer, Analyst...) assumes a clean CSV already
exists. This file's only job: turn OpenAQ's paginated JSON API into
that CSV.
"""

import os
import csv
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("OPENAQ_API_KEY")
SENSOR_ID = 23534  # New Delhi PM2.5
BASE_URL = f"https://api.openaq.org/v3/sensors/{SENSOR_ID}/days"


def fetch_page(page: int, datetime_from: str, datetime_to: str, limit: int = 1000) -> dict:
    """Fetch one page of daily-aggregated results."""
    params = {
        "datetime_from": datetime_from,
        "datetime_to": datetime_to,
        "limit": limit,
        "page": page,
    }
    headers = {"X-API-Key": API_KEY}
    response = requests.get(BASE_URL, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_all_days(datetime_from: str, datetime_to: str) -> list:
    """Loop through pages until a page comes back with no results.

    This is the same pagination shape you've already seen in the
    Analyst's sandbox loop -- keep going until there's nothing left,
    never assume everything fits in one request.
    """
    all_results = []
    page = 1
    while True:
        data = fetch_page(page=page, datetime_from=datetime_from, datetime_to=datetime_to)
        results = data.get("results", [])
        if not results:
            break
        all_results.extend(results)
        page += 1
    return all_results


def extract_row(result: dict) -> dict:
    """Pull just the date and PM2.5 value out of one API result item.
    Everything else (coverage stats, flags, etc.) is dropped -- the
    Profiler only needs a clean, flat row."""
    date = result["period"]["datetimeFrom"]["local"]
    pm25_value = result["value"]
    return {"date": date, "pm25_value": pm25_value}


def write_csv(rows: list, path: str = "delhi_aqi.csv"):
    """Write rows to CSV. Guards against an empty result set instead of
    silently writing a header-only file and confusing the next step."""
    if not rows:
        print("No rows to write -- check your date range and sensor ID.")
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "pm25_value"])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    results = fetch_all_days(datetime_from="2025-01-01", datetime_to="2025-12-31")
    rows = [extract_row(r) for r in results]
    write_csv(rows)
    print(f"Wrote {len(rows)} rows to delhi_aqi.csv")