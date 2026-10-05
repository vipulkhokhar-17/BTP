"""Google Search Console data export.

Setup (once):
  1. Verify https://vip-ul.codes in Search Console (Domain property via DNS is easiest).
  2. In Google Cloud, enable the "Google Search Console API", create a service
     account and download its JSON key.
  3. In Search Console → Settings → Users and permissions, add the service
     account's email as a user (Restricted is enough).
  4. pip install google-api-python-client google-auth
  5. export GSC_CREDENTIALS=/path/to/key.json

Search Console data lags by 2–3 days, so fetch up to (today - 3 days).
"""

import csv
import os
from pathlib import Path

COLUMNS = ["date", "page", "clicks", "impressions", "ctr", "position"]


def _service(credentials_path):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def fetch(site_url, start_date, end_date, dimensions=("date", "page"), credentials_path=None):
    """Yield rows as dicts. Pages with zero impressions are simply absent."""
    service = _service(credentials_path or os.environ["GSC_CREDENTIALS"])
    start_row = 0
    while True:
        body = {"startDate": start_date, "endDate": end_date, "dimensions": list(dimensions),
                "rowLimit": 25000, "startRow": start_row, "dataState": "final"}
        resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
        rows = resp.get("rows", [])
        for r in rows:
            row = dict(zip(dimensions, r["keys"]))
            row.update(clicks=r["clicks"], impressions=r["impressions"],
                       ctr=r["ctr"], position=r["position"])
            yield row
        if len(rows) < 25000:
            return
        start_row += len(rows)


def save_csv(rows, path, columns=COLUMNS):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def load_csv(path):
    with open(path, newline="") as f:
        return [{**r, "clicks": float(r["clicks"]), "impressions": float(r["impressions"]),
                 "position": float(r["position"])} for r in csv.DictReader(f)]
