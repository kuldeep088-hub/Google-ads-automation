from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Google Ads
    GOOGLE_ADS_DEVELOPER_TOKEN: str = ""
    GOOGLE_ADS_CLIENT_ID: str = ""
    GOOGLE_ADS_CLIENT_SECRET: str = ""
    GOOGLE_ADS_REFRESH_TOKEN: str = ""
    GOOGLE_ADS_LOGIN_CUSTOMER_ID: str = ""
    GOOGLE_ADS_TARGET_CUSTOMER_ID: str = ""

    # Database
    DATABASE_URL: str = "sqlite:///./ads_automation.db"

    # Email
    EMAIL_BACKEND: str = "smtp"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SENDGRID_API_KEY: str = ""
    ALERT_EMAIL_FROM: str = ""
    ALERT_EMAIL_TO: str = ""

    # Slack
    SLACK_WEBHOOK_URL: str = ""

    # Google Sheets
    GSPREAD_SERVICE_ACCOUNT_JSON: str = "./credentials/gspread_service_account.json"

    # App
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def alert_recipients(self) -> list[str]:
        return [e.strip() for e in self.ALERT_EMAIL_TO.split(",") if e.strip()]


settings = Settings()
