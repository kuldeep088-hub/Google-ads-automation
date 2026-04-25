import os
import tempfile
import textwrap

import pytest

from app.ingestion.csv_parser import parse_campaign_csv


def _write_csv(content: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w")
    tmp.write(textwrap.dedent(content))
    tmp.close()
    return tmp.name


def test_valid_csv_parsed():
    path = _write_csv("""
        campaign_name,daily_budget_usd,headline_1,headline_2,headline_3,description_1,description_2,final_url,keyword_1,keyword_1_match
        Test Campaign,10.00,Buy Now,Best Deal,Shop Today,Amazing products for you,Free shipping available,https://example.com,test keyword,BROAD
    """)
    try:
        rows, errors = parse_campaign_csv(path)
        assert len(rows) == 1
        assert rows[0].campaign_name == "Test Campaign"
        assert rows[0].daily_budget_usd == 10.0
        assert rows[0].keywords == [("test keyword", "BROAD")]
        assert not errors
    finally:
        os.unlink(path)


def test_empty_csv_returns_no_rows():
    path = _write_csv("campaign_name,daily_budget_usd\n")
    try:
        rows, errors = parse_campaign_csv(path)
        assert rows == []
    finally:
        os.unlink(path)


def test_headline_truncated_at_30():
    path = _write_csv("""
        campaign_name,daily_budget_usd,headline_1,headline_2,headline_3,description_1,description_2,final_url
        Camp,5.00,This headline is way too long and should be cut,H2,H3,D1,D2,https://x.com
    """)
    try:
        rows, errors = parse_campaign_csv(path)
        assert len(rows[0].headline_1) <= 30
    finally:
        os.unlink(path)
