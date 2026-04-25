from google.ads.googleads.client import GoogleAdsClient
from app.config import settings


class AdsAuthManager:
    _client: GoogleAdsClient | None = None

    @classmethod
    def get_client(cls) -> GoogleAdsClient:
        if cls._client is None:
            config = {
                "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                "client_id": settings.GOOGLE_ADS_CLIENT_ID,
                "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
                "refresh_token": settings.GOOGLE_ADS_REFRESH_TOKEN,
                "use_proto_plus": True,
            }
            if settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID:
                config["login_customer_id"] = settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID
            cls._client = GoogleAdsClient.load_from_dict(config)
        return cls._client

    @classmethod
    def invalidate(cls) -> None:
        cls._client = None
