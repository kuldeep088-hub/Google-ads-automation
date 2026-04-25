import gspread
from app.google_ads.campaign_service import CampaignRow
from app.ingestion.csv_parser import parse_campaign_csv
import tempfile
import csv
import os


def fetch_from_google_sheets(
    sheet_url: str,
    credentials_json_path: str,
) -> tuple[list[CampaignRow], list[str]]:
    gc = gspread.service_account(filename=credentials_json_path)
    sh = gc.open_by_url(sheet_url)
    ws = sh.get_worksheet(0)
    records = ws.get_all_records()

    if not records:
        return [], ["Google Sheet is empty"]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as tmp:
        writer = csv.DictWriter(tmp, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
        tmp_path = tmp.name

    try:
        return parse_campaign_csv(tmp_path)
    finally:
        os.unlink(tmp_path)
