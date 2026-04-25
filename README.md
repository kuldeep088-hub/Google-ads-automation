# Google Ads Automation

A full-stack Python automation platform for Google Ads — bid management, budget control, campaign creation, ML-powered predictions, and a live web dashboard.

---

## Features

- **Bid Management** — CPA-based, time-of-day, and device bid adjustments via rule engine
- **ML Bid Prediction** — GradientBoostingRegressor predicts optimal CPC bids; falls back to CPA rules when data is sparse
- **Negative Keyword Mining** — automatically detects zero-conversion waste terms and adds them as negatives
- **Keyword Promotion** — promotes high-converting search terms to exact-match keywords
- **Quality Score Monitor** — snapshots QS daily, auto-pauses keywords with QS ≤ 3
- **Budget Management** — monthly spend caps, pause-on-overspend, budget redistribution
- **Campaign Creation** — bulk create campaigns from CSV or Google Sheets
- **Reporting & Alerts** — daily/weekly email reports, anomaly detection, Slack notifications
- **Web Dashboard** — FastAPI + Jinja2 + Chart.js, no separate JS build step

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Web framework | FastAPI + Uvicorn |
| Templates | Jinja2 + Chart.js (CDN) |
| Database | SQLAlchemy 2.0 + SQLite (dev) / PostgreSQL (prod) |
| Scheduler | APScheduler 3.x |
| Google Ads API | google-ads 24.1.0 (API v17) |
| ML | scikit-learn (GradientBoostingRegressor) |
| Alerts | SMTP / SendGrid + Slack webhooks |

---

## Project Structure

```
├── app/
│   ├── api/               # FastAPI routers + dashboard
│   ├── automation/        # Rule engine + action executor
│   ├── db/                # SQLAlchemy ORM models
│   ├── google_ads/        # Google Ads API services
│   ├── ingestion/         # CSV + Google Sheets parsers
│   ├── jobs/              # APScheduler job functions
│   ├── ml/                # ML bid predictor
│   ├── notifications/     # Email + Slack senders
│   └── templates/         # Jinja2 HTML templates
├── static/                # CSS + JS
├── tests/
├── .env.example
├── requirements.txt
└── run.py
```

---

## Setup

### 1. Clone and create virtual environment

```bash
git clone https://github.com/kuldeep088-hub/Google-ads-automation.git
cd Google-ads-automation

# Python 3.11 required (google-ads is incompatible with 3.14+)
py -3.11 -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure credentials

```bash
copy .env.example .env
```

Edit `.env` and fill in:

| Variable | Where to get it |
|----------|----------------|
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Google Ads → Tools → API Center |
| `GOOGLE_ADS_CLIENT_ID` | Google Cloud Console → OAuth 2.0 credentials |
| `GOOGLE_ADS_CLIENT_SECRET` | Google Cloud Console → OAuth 2.0 credentials |
| `GOOGLE_ADS_REFRESH_TOKEN` | Run the OAuth flow (see below) |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | Your Manager account ID (digits only) |
| `GOOGLE_ADS_TARGET_CUSTOMER_ID` | Your Advertiser account ID (digits only) |

**Generate refresh token:**

```bash
pip install google-auth-oauthlib
python -c "
from google_auth_oauthlib.flow import InstalledAppFlow
flow = InstalledAppFlow.from_client_config(
    {'installed': {'client_id': 'YOUR_CLIENT_ID', 'client_secret': 'YOUR_CLIENT_SECRET',
     'redirect_uris': ['http://localhost:8085'], 'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
     'token_uri': 'https://oauth2.googleapis.com/token'}},
    scopes=['https://www.googleapis.com/auth/adwords']
)
creds = flow.run_local_server(port=8085)
print('Refresh token:', creds.refresh_token)
"
```

### 4. Initialize database

```bash
python -c "from app.database import engine; from app.db.models import Base; Base.metadata.create_all(engine)"
```

### 5. Start the app

```bash
python run.py
```

Open **http://localhost:8000**

---

## Dashboard Pages

| URL | Page |
|-----|------|
| `/` | KPI overview + 7-day trend charts |
| `/campaigns` | Campaign table with status and spend |
| `/budgets` | Budget utilization + monthly cap progress |
| `/rules` | Automation rule management |
| `/reports/daily` | Per-campaign bar charts + anomalies |
| `/reports/weekly` | Weekly trend line charts |
| `/jobs` | Job run history + audit log |
| `/advanced/negative-keywords` | Auto-mined negative keywords |
| `/advanced/promoted-keywords` | Promoted search terms |
| `/advanced/quality-scores` | QS distribution + auto-paused keywords |
| `/advanced/ml-predictions` | ML bid recommendations |

---

## Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| `bid_management` | Every hour | CPA + device bid rules |
| `tod_bid_rules` | Every 15 min | Time-of-day bid adjustments |
| `budget_management` | Every 2 hours | Cap enforcement + redistribution |
| `daily_reporting` | 06:00 UTC | Snapshot + email report |
| `weekly_reporting` | Mon 07:00 UTC | Weekly trend report |
| `negative_keyword_mining` | 04:00 UTC | Block waste search terms |
| `keyword_promotion` | 04:30 UTC | Promote converting search terms |
| `ml_bid_optimization` | Every 3 hours | ML bid scoring |
| `quality_score_monitor` | 05:00 UTC | QS snapshot + auto-pause |

All jobs can be triggered manually from `/jobs`.

---

## ML Bid Prediction

The ML model trains on `QualityScoreHistory` records. It needs at least **50 samples** before activating — until then it falls back to CPA-rule logic.

To auto-apply ML bid predictions (disabled by default):

```python
# app/jobs/ml_bid_job.py  line 12
APPLY_PREDICTIONS = True   # change from False
```

---

## Environment Variables

See `.env.example` for the full list. Key optional settings:

```env
# Email alerts
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your_app_password

# Slack alerts
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# PostgreSQL (production)
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/ads_automation
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## License

MIT
