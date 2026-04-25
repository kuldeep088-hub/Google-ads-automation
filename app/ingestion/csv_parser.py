import pandas as pd
from app.google_ads.campaign_service import CampaignRow


def parse_campaign_csv(file_path: str) -> tuple[list[CampaignRow], list[str]]:
    df = pd.read_csv(file_path, dtype=str).fillna("")
    rows: list[CampaignRow] = []
    errors: list[str] = []

    for idx, record in enumerate(df.to_dict("records")):
        try:
            keywords = []
            for i in range(1, 6):
                kw = record.get(f"keyword_{i}", "").strip()
                match = record.get(f"keyword_{i}_match", "BROAD").strip().upper() or "BROAD"
                if kw:
                    keywords.append((kw, match))

            row = CampaignRow(
                campaign_name=record["campaign_name"].strip(),
                campaign_type=record.get("campaign_type", "SEARCH").strip().upper() or "SEARCH",
                daily_budget_usd=float(record.get("daily_budget_usd", "1") or "1"),
                bid_strategy=record.get("bid_strategy", "MANUAL_CPC").strip().upper() or "MANUAL_CPC",
                ad_group_name=record.get("ad_group_name", "").strip() or record["campaign_name"].strip(),
                keywords=keywords,
                headline_1=record.get("headline_1", "")[:30],
                headline_2=record.get("headline_2", "")[:30],
                headline_3=record.get("headline_3", "")[:30],
                description_1=record.get("description_1", "")[:90],
                description_2=record.get("description_2", "")[:90],
                final_url=record.get("final_url", "").strip(),
                geo_target=record.get("geo_target", "US").strip() or "US",
                language=record.get("language", "en").strip() or "en",
            )
            rows.append(row)
        except Exception as e:
            errors.append(f"Row {idx + 2}: {e}")

    return rows, errors
