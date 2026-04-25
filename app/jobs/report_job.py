import json
import logging
from datetime import date, datetime

from app.database import SessionLocal
from app.db.models import JobRun, PerformanceSnapshot, ReportCache

logger = logging.getLogger(__name__)

MICROS = 1_000_000


def run_daily_reporting(triggered_by: str = "scheduler"):
    db = SessionLocal()
    job_run = JobRun(
        job_name="daily_reporting",
        status="running",
        started_at=datetime.utcnow(),
        triggered_by=triggered_by,
    )
    db.add(job_run)
    db.commit()

    try:
        from app.google_ads.report_service import ReportService
        from app.notifications.email_sender import EmailSender
        from app.notifications.slack_sender import SlackSender
        from app.config import settings

        service = ReportService()
        today = date.today().strftime("%Y-%m-%d")

        summary = service.get_daily_summary(today)
        campaigns = service.get_campaign_performance("YESTERDAY")
        anomalies = service.get_top_anomalies(threshold_pct=0.30)

        _save_snapshot(db, today, summary, campaigns)
        _cache_report(db, "daily_summary", today, {"summary": summary, "campaigns": campaigns, "anomalies": anomalies})

        html = _build_daily_email(summary, campaigns, anomalies)
        if settings.alert_recipients:
            EmailSender().send(
                subject=f"Google Ads Daily Report — {today}",
                body_html=html,
                recipients=settings.alert_recipients,
            )

        if anomalies:
            text = "\n".join(
                f"• {a['metric']}: {a['direction']} {a['deviation_pct']}% (today ${a['today_value']} vs avg ${a['avg_value']})"
                for a in anomalies
            )
            SlackSender().send(f":warning: *Google Ads Anomalies Detected* ({today})\n{text}")

        job_run.status = "success"
        logger.info("Daily reporting completed for %s", today)

    except Exception as exc:
        job_run.status = "failed"
        job_run.error_summary = json.dumps([str(exc)])
        logger.exception("daily_reporting job failed")
    finally:
        job_run.finished_at = datetime.utcnow()
        db.commit()
        db.close()


def run_weekly_reporting(triggered_by: str = "scheduler"):
    db = SessionLocal()
    job_run = JobRun(
        job_name="weekly_reporting",
        status="running",
        started_at=datetime.utcnow(),
        triggered_by=triggered_by,
    )
    db.add(job_run)
    db.commit()

    try:
        from app.google_ads.report_service import ReportService
        from app.notifications.email_sender import EmailSender
        from app.config import settings

        service = ReportService()
        today = date.today().strftime("%Y-%m-%d")

        campaigns = service.get_campaign_performance("LAST_7_DAYS")
        keywords = service.get_keyword_performance("LAST_7_DAYS")

        _cache_report(db, "weekly_summary", today, {"campaigns": campaigns, "keywords": keywords})

        html = _build_weekly_email(campaigns, keywords)
        if settings.alert_recipients:
            EmailSender().send(
                subject=f"Google Ads Weekly Summary — Week of {today}",
                body_html=html,
                recipients=settings.alert_recipients,
            )

        job_run.status = "success"
        logger.info("Weekly reporting completed")

    except Exception as exc:
        job_run.status = "failed"
        job_run.error_summary = json.dumps([str(exc)])
        logger.exception("weekly_reporting job failed")
    finally:
        job_run.finished_at = datetime.utcnow()
        db.commit()
        db.close()


def _save_snapshot(db, today: str, summary: dict, campaigns: list[dict]):
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    snapshot_date = date.fromisoformat(today)
    conv = summary.get("conversions", 0) or 0.001
    account_snap = PerformanceSnapshot(
        snapshot_date=snapshot_date,
        entity_type="account",
        entity_id="account",
        impressions=summary.get("impressions", 0),
        clicks=summary.get("clicks", 0),
        cost_micros=summary.get("cost_micros", 0),
        conversions=summary.get("conversions", 0),
        ctr=summary.get("ctr", 0),
        cpa_micros=int(summary.get("cost_micros", 0) / conv),
    )
    try:
        db.merge(account_snap)
        db.commit()
    except Exception:
        db.rollback()


def _cache_report(db, report_type: str, report_date: str, payload: dict):
    from app.db.models import ReportCache
    existing = (
        db.query(ReportCache)
        .filter(ReportCache.report_type == report_type, ReportCache.report_date == date.fromisoformat(report_date))
        .first()
    )
    if existing:
        existing.payload = json.dumps(payload)
        existing.generated_at = datetime.utcnow()
    else:
        db.add(ReportCache(
            report_type=report_type,
            report_date=date.fromisoformat(report_date),
            payload=json.dumps(payload),
        ))
    db.commit()


def _build_daily_email(summary: dict, campaigns: list[dict], anomalies: list[dict]) -> str:
    anomaly_rows = "".join(
        f"<tr><td>{a['metric']}</td><td style='color:{'red' if a['direction']=='spike' else 'orange'}'>"
        f"{a['direction'].upper()} {a['deviation_pct']}%</td>"
        f"<td>${a['today_value']}</td><td>${a['avg_value']}</td></tr>"
        for a in anomalies
    )
    campaign_rows = "".join(
        f"<tr><td>{c['campaign_name']}</td><td>{c['status']}</td>"
        f"<td>${c['cost_usd']:.2f}</td><td>{c['clicks']}</td>"
        f"<td>{c['conversions']:.1f}</td><td>{c['ctr']}%</td></tr>"
        for c in campaigns[:20]
    )
    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:800px;margin:auto">
    <h2>Google Ads Daily Report — {summary.get('date', '')}</h2>
    <table border="1" cellpadding="8" style="border-collapse:collapse;width:100%">
      <tr><th>Impressions</th><th>Clicks</th><th>Cost</th><th>Conversions</th><th>CPA</th><th>CTR</th></tr>
      <tr>
        <td>{summary.get('impressions',0):,}</td>
        <td>{summary.get('clicks',0):,}</td>
        <td>${summary.get('cost_usd',0):.2f}</td>
        <td>{summary.get('conversions',0):.1f}</td>
        <td>${summary.get('cpa_usd',0):.2f}</td>
        <td>{summary.get('ctr',0)*100:.2f}%</td>
      </tr>
    </table>
    {'<h3>⚠️ Anomalies</h3><table border="1" cellpadding="8" style="border-collapse:collapse"><tr><th>Metric</th><th>Direction</th><th>Today</th><th>7d Avg</th></tr>' + anomaly_rows + '</table>' if anomalies else ''}
    <h3>Campaign Performance</h3>
    <table border="1" cellpadding="8" style="border-collapse:collapse;width:100%">
      <tr><th>Campaign</th><th>Status</th><th>Cost</th><th>Clicks</th><th>Conversions</th><th>CTR</th></tr>
      {campaign_rows}
    </table>
    </body></html>
    """


def _build_weekly_email(campaigns: list[dict], keywords: list[dict]) -> str:
    campaign_rows = "".join(
        f"<tr><td>{c['campaign_name']}</td><td>${c['cost_usd']:.2f}</td>"
        f"<td>{c['clicks']}</td><td>{c['conversions']:.1f}</td>"
        f"<td>{c['ctr']}%</td><td>${c.get('cpa_usd',0):.2f}</td></tr>"
        for c in sorted(campaigns, key=lambda x: x['cost_usd'], reverse=True)[:15]
    )
    kw_rows = "".join(
        f"<tr><td>{k['keyword']}</td><td>{k['match_type']}</td>"
        f"<td>${k['cost_usd']:.2f}</td><td>{k['clicks']}</td>"
        f"<td>{k['conversions']:.1f}</td><td>{k['ctr']}%</td></tr>"
        for k in sorted(keywords, key=lambda x: x['cost_usd'], reverse=True)[:20]
    )
    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:900px;margin:auto">
    <h2>Google Ads Weekly Summary</h2>
    <h3>Top Campaigns (Last 7 Days)</h3>
    <table border="1" cellpadding="8" style="border-collapse:collapse;width:100%">
      <tr><th>Campaign</th><th>Cost</th><th>Clicks</th><th>Conversions</th><th>CTR</th><th>CPA</th></tr>
      {campaign_rows}
    </table>
    <h3>Top Keywords (Last 7 Days)</h3>
    <table border="1" cellpadding="8" style="border-collapse:collapse;width:100%">
      <tr><th>Keyword</th><th>Match</th><th>Cost</th><th>Clicks</th><th>Conversions</th><th>CTR</th></tr>
      {kw_rows}
    </table>
    </body></html>
    """
